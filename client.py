"""Async wrapper around the Google Calendar API using existing google-workspace OAuth."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from .config import CalendarConfig
from .exceptions import (
    CalendarAPIError,
    CalendarAuthError,
    CalendarPluginError,
    EventNotFoundError,
)
from .models import EventCreateRequest, EventResponse

__all__ = ["GoogleCalendarClient"]

logger = logging.getLogger(__name__)

_MISSING_TOKEN_HINT = (
    "Run: python data/skills/productivity/google-workspace/scripts/setup.py --auth-url "
    "(or see google-workspace SKILL.md)"
)


def _oauth_lock(token_path):
    """Import the shared OAuth side-car lock, tolerating an absent common module."""
    try:
        import sys
        from pathlib import Path as _Path
        common_dir = _Path(__file__).resolve().parent.parent / "common"
        if str(common_dir.parent) not in sys.path:
            sys.path.insert(0, str(common_dir.parent))
        from common.profile_resolver import google_token_lock
        return google_token_lock(token_path)
    except Exception:  # noqa: BLE001 — never break auth on a lock import failure
        from contextlib import nullcontext
        return nullcontext()


def _http_error(exc: Exception) -> CalendarPluginError:
    status = getattr(getattr(exc, "resp", None), "status", None)
    msg = "Google Calendar API request failed"
    try:
        content = getattr(exc, "content", b"")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if content:
            payload = json.loads(content)
            err = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(err, dict) and err.get("message"):
                msg = str(err["message"])
            elif isinstance(payload, dict) and payload.get("message"):
                msg = str(payload["message"])
    except Exception:  # noqa: BLE001
        pass

    if status in (401, 403):
        return CalendarAuthError(
            msg, code="auth_error", status=status, hint=_MISSING_TOKEN_HINT
        )
    if status == 404:
        return EventNotFoundError(msg, code="not_found", status=status)
    return CalendarAPIError(msg, code="api_error", status=status)


class GoogleCalendarClient:
    """Google Calendar client that reuses google-workspace token files."""

    def __init__(self, config: CalendarConfig) -> None:
        self._config = config

    @property
    def config(self) -> CalendarConfig:
        return self._config

    def _service(self):
        token_path = self._config.token_path
        if not token_path.exists():
            raise CalendarAuthError(
                "Google Workspace token is missing.",
                code="missing_token",
                hint=_MISSING_TOKEN_HINT,
            )

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except Exception as exc:  # noqa: BLE001
            raise CalendarAPIError(
                "Google API libraries are unavailable. Install hermes-agent[google].",
                code="missing_dependency",
                hint="pip install hermes-agent[google]",
            ) from exc

        try:
            creds = Credentials.from_authorized_user_file(str(token_path))
        except Exception as exc:  # noqa: BLE001
            raise CalendarAuthError(
                "Failed to load Google Workspace token.",
                code="invalid_token",
                hint=_MISSING_TOKEN_HINT,
            ) from exc

        if creds.expired and creds.refresh_token:
            # Same OAuth race mitigation as gmail client: refresh + persist
            # only while holding the side-car file lock.
            with _oauth_lock(token_path):
                try:
                    reloaded = Credentials.from_authorized_user_file(str(token_path))
                    if not reloaded.expired:
                        creds = reloaded
                    else:
                        creds = self._refresh_and_persist(creds, token_path)
                except CalendarAuthError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.debug("google-calendar: token reload after lock failed: %s", exc)
                    creds = self._refresh_and_persist(creds, token_path)

        if not creds.valid:
            raise CalendarAuthError(
                "Google Workspace token is invalid.",
                code="invalid_token",
                hint=_MISSING_TOKEN_HINT,
            )

        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _refresh_and_persist(self, creds, token_path):
        """Refresh the token and persist it, called while holding the OAuth lock."""
        from google.auth.transport.requests import Request

        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001
            raise CalendarAuthError(
                "Failed to refresh Google Workspace token.",
                code="refresh_failed",
                hint=_MISSING_TOKEN_HINT,
            ) from exc
        try:
            payload = json.loads(creds.to_json())
            if not payload.get("type"):
                payload["type"] = "authorized_user"
            token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if os.name != "nt":
                try:
                    token_path.chmod(0o600)
                except Exception:  # noqa: BLE001
                    pass
            return creds
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "google-calendar: failed to persist refreshed token: %s", exc
            )
            return creds

    def _run_sync(self, fn):
        try:
            return fn()
        except (CalendarAuthError, CalendarAPIError, EventNotFoundError):
            raise
        except Exception as exc:  # noqa: BLE001
            try:
                from googleapiclient.errors import HttpError
            except Exception:  # noqa: BLE001
                HttpError = ()  # type: ignore[assignment]
            if isinstance(exc, HttpError):
                raise _http_error(exc) from exc
            raise CalendarAPIError(
                str(exc) or "Google Calendar request failed"
            ) from exc

    async def _call(self, fn):
        return await asyncio.to_thread(self._run_sync, fn)

    @staticmethod
    def _event_body(payload: EventCreateRequest) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "summary": payload.summary,
            "start": {"dateTime": payload.start},
            "end": {"dateTime": payload.end},
        }
        if payload.description:
            body["description"] = payload.description
        if payload.location:
            body["location"] = payload.location
        if payload.attendees:
            body["attendees"] = [{"email": email} for email in payload.attendees]
        return body

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 20,
        q: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        max_results = max(1, min(int(max_results or 20), 100))

        def _op():
            service = self._service()
            params: Dict[str, Any] = {
                "calendarId": calendar_id or self._config.default_calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
            if q:
                params["q"] = q
            result = service.events().list(**params).execute() or {}
            items = [
                EventResponse.from_api(e).model_dump() for e in result.get("items", [])
            ]
            return {
                "items": items,
                "nextPageToken": result.get("nextPageToken"),
                "calendar_id": params["calendarId"],
            }

        return await self._call(_op)

    async def create_event(self, payload: EventCreateRequest) -> Dict[str, Any]:
        def _op():
            service = self._service()
            body = self._event_body(payload)
            result = (
                service.events()
                .insert(
                    calendarId=payload.calendar_id or self._config.default_calendar_id,
                    body=body,
                )
                .execute()
                or {}
            )
            return EventResponse.from_api(result).model_dump()

        return await self._call(_op)

    async def delete_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        if not event_id or not str(event_id).strip():
            raise CalendarAPIError(
                "event_id is required", code="invalid_input", status=400
            )

        def _op():
            service = self._service()
            service.events().delete(
                calendarId=calendar_id or self._config.default_calendar_id,
                eventId=event_id,
            ).execute()
            return {
                "deleted": True,
                "event_id": event_id,
                "calendar_id": calendar_id or "primary",
            }

        return await self._call(_op)

    async def get_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "configured": self._config.has_token,
            "calendar_id": self._config.default_calendar_id,
        }
        if not self._config.has_token:
            status["error"] = "Google Workspace token is missing."
            status["hint"] = _MISSING_TOKEN_HINT
            return status
        try:
            await self.list_events(
                max_results=1, calendar_id=self._config.default_calendar_id
            )
            return status
        except CalendarPluginError as exc:
            status["error"] = str(exc)
            if exc.hint:
                status["hint"] = exc.hint
            if isinstance(exc, CalendarAuthError):
                status["configured"] = False
            return status

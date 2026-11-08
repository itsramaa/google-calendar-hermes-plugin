"""Tool handlers for Google Calendar. Return structured tool_result/tool_error."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Coroutine

__all__ = [
    "handle_google_calendar_list_events",
    "handle_google_calendar_create_event",
    "handle_google_calendar_delete_event",
]

logger = logging.getLogger(__name__)

try:
    from tools.registry import tool_error, tool_result
except Exception:  # pragma: no cover - test/runtime fallback

    def tool_result(data=None, **kwargs):  # type: ignore[no-redef]
        payload = {"ok": True}
        if data is not None:
            payload["data"] = data
        payload.update(kwargs)
        return json.dumps(payload, ensure_ascii=False)

    def tool_error(message, **kwargs):  # type: ignore[no-redef]
        payload = {"ok": False, "error": str(message)}
        payload.update(kwargs)
        return json.dumps(payload, ensure_ascii=False)


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Handler called inside an active loop (unusual for sync handlers); run in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _client():
    from ..client import GoogleCalendarClient
    from ..config import CalendarConfig

    return GoogleCalendarClient(CalendarConfig.from_env())


def _plugin_err(exc: Exception) -> str:
    from ..exceptions import CalendarAuthError, CalendarPluginError, EventNotFoundError

    if isinstance(exc, CalendarPluginError):
        details: dict[str, Any] = {}
        if exc.code:
            details["code"] = exc.code
        if exc.status:
            details["status"] = exc.status
        if exc.hint:
            details["hint"] = exc.hint
        if isinstance(exc, EventNotFoundError):
            details.setdefault("code", "not_found")
        if isinstance(exc, CalendarAuthError):
            details.setdefault("code", "auth_error")
        return tool_error(str(exc), **details)
    return tool_error(str(exc) or "Calendar operation failed")


def handle_google_calendar_list_events(args: dict, **kwargs: Any) -> str:
    del kwargs
    args = args or {}
    try:
        result = _run(
            _client().list_events(
                time_min=args.get("time_min"),
                time_max=args.get("time_max"),
                max_results=args.get("max_results", 20),
                q=args.get("query"),
                calendar_id=args.get("calendar_id") or "primary",
            )
        )
        return tool_result(result)
    except Exception as exc:  # noqa: BLE001
        return _plugin_err(exc)


def handle_google_calendar_create_event(args: dict, **kwargs: Any) -> str:
    del kwargs
    args = args or {}
    from ..models import EventCreateRequest

    try:
        payload = EventCreateRequest(
            summary=args.get("summary", ""),
            start=args.get("start", ""),
            end=args.get("end", ""),
            description=args.get("description"),
            location=args.get("location"),
            attendees=args.get("attendees"),
            calendar_id=args.get("calendar_id") or "primary",
        )
    except Exception as exc:  # noqa: BLE001
        return tool_error(str(exc), code="invalid_input", status=400)

    try:
        result = _run(_client().create_event(payload))
        return tool_result(result)
    except Exception as exc:  # noqa: BLE001
        return _plugin_err(exc)


def handle_google_calendar_delete_event(args: dict, **kwargs: Any) -> str:
    del kwargs
    args = args or {}
    event_id = args.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        return tool_error(
            "event_id must be a non-empty string", code="invalid_input", status=400
        )
    if not args.get("confirmed"):
        return tool_error(
            "Deleting a calendar event is destructive. Set confirmed=true only after the user explicitly confirms.",
            code="confirmation_required",
            requires_confirmation=True,
            action="delete_event",
            event_id=event_id,
        )
    try:
        result = _run(
            _client().delete_event(
                event_id.strip(), calendar_id=args.get("calendar_id") or "primary"
            )
        )
        return tool_result(result)
    except Exception as exc:  # noqa: BLE001
        return _plugin_err(exc)

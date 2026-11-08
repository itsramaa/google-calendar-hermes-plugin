"""Google Calendar dashboard plugin — backend API routes.

Mounted at /api/plugins/google-calendar/ by the dashboard plugin system.
The api file is exec'd as a standalone module by the dashboard server, so
the plugin package is located dynamically.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


def _load() -> Any:
    """Import the google-calendar plugin package in supported contexts."""
    for name in ("hermes_plugins.google_calendar", "google_calendar"):
        try:
            return importlib.import_module(name)
        except Exception:
            pass
    # The on-disk plugin dir is hyphenated (google-calendar), so `import
    # google_calendar` only works when the dashboard runtime has registered it.
    # Fallback: load the directory directly under the same alias the tests use.
    import importlib.util

    plugin_root = Path(__file__).resolve().parent.parent
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    spec = importlib.util.spec_from_file_location(
        "google_calendar",
        plugin_root / "__init__.py",
        submodule_search_locations=[str(plugin_root)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["google_calendar"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_pkg = _load()
_pkg_name = _pkg.__name__
CalendarConfig = importlib.import_module(f"{_pkg_name}.config").CalendarConfig
GoogleCalendarClient = importlib.import_module(
    f"{_pkg_name}.client"
).GoogleCalendarClient
_models = importlib.import_module(f"{_pkg_name}.models")
EventCreateRequest = _models.EventCreateRequest
_exceptions = importlib.import_module(f"{_pkg_name}.exceptions")
CalendarPluginError = _exceptions.CalendarPluginError
CalendarAuthError = _exceptions.CalendarAuthError
EventNotFoundError = _exceptions.EventNotFoundError


def _run(coro):
    return asyncio.run(coro)


def _client() -> Any:
    return GoogleCalendarClient(CalendarConfig.from_env())


def _error_shape(exc: Exception) -> Dict[str, Any]:
    config = CalendarConfig.from_env()
    data: Dict[str, Any] = {
        "configured": config.has_token,
        "calendar_id": config.default_calendar_id,
        "error": str(exc),
    }
    if isinstance(exc, CalendarPluginError):
        if exc.hint:
            data["hint"] = exc.hint
        if isinstance(exc, CalendarAuthError):
            data["configured"] = False
    return data


@router.get("/status")
async def status() -> Dict[str, Any]:
    try:
        return await asyncio.to_thread(lambda: _run(_client().get_status()))
    except Exception as exc:  # noqa: BLE001
        return _error_shape(exc)


@router.get("/events")
async def events(
    time_min: Optional[str] = Query(default=None),
    time_max: Optional[str] = Query(default=None),
    max_results: int = Query(default=20, ge=1, le=100),
    q: Optional[str] = Query(default=None),
    calendar_id: str = Query(default="primary"),
) -> Dict[str, Any]:
    config = CalendarConfig.from_env()
    if not config.has_token:
        return {
            "configured": False,
            "calendar_id": config.default_calendar_id,
            "data": [],
            "error": "Google Workspace token is missing.",
            "hint": "Run: python data/skills/productivity/google-workspace/scripts/setup.py --auth-url (or see google-workspace SKILL.md)",
        }
    try:
        result = await asyncio.to_thread(
            lambda: _run(
                _client().list_events(
                    time_min=time_min,
                    time_max=time_max,
                    max_results=max_results,
                    q=q,
                    calendar_id=calendar_id or config.default_calendar_id,
                )
            )
        )
        return {"configured": True, "error": None, **result}
    except CalendarAuthError as exc:
        return _error_shape(exc)
    except Exception as exc:  # noqa: BLE001
        return _error_shape(exc)


class CreateEventBody(BaseModel):
    summary: str
    start: str
    end: str
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    calendar_id: str = "primary"


@router.post("/events")
async def create_event(body: CreateEventBody) -> Dict[str, Any]:
    try:
        payload = EventCreateRequest(
            summary=body.summary,
            start=body.start,
            end=body.end,
            description=body.description,
            location=body.location,
            attendees=body.attendees,
            calendar_id=body.calendar_id or "primary",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return await asyncio.to_thread(lambda: _run(_client().create_event(payload)))
    except CalendarAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except CalendarPluginError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    calendar_id: str = Query(default="primary"),
) -> Dict[str, Any]:
    try:
        return await asyncio.to_thread(
            lambda: _run(
                _client().delete_event(event_id, calendar_id=calendar_id or "primary")
            )
        )
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CalendarAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except CalendarPluginError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

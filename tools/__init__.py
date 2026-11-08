"""Register Google Calendar tools with the Hermes plugin context."""

from __future__ import annotations

import logging
from typing import Any

from .handlers import (
    handle_google_calendar_create_event,
    handle_google_calendar_delete_event,
    handle_google_calendar_list_events,
)
from .schemas import (
    GOOGLE_CALENDAR_CREATE_EVENT_SCHEMA,
    GOOGLE_CALENDAR_DELETE_EVENT_SCHEMA,
    GOOGLE_CALENDAR_LIST_EVENTS_SCHEMA,
)

__all__ = ["register_tools"]

logger = logging.getLogger(__name__)

_TOOLS = [
    (
        "google_calendar_list_events",
        GOOGLE_CALENDAR_LIST_EVENTS_SCHEMA,
        handle_google_calendar_list_events,
        "List Google Calendar events (ISO 8601 times with timezone).",
    ),
    (
        "google_calendar_create_event",
        GOOGLE_CALENDAR_CREATE_EVENT_SCHEMA,
        handle_google_calendar_create_event,
        "Create a Google Calendar event (start/end must include timezone).",
    ),
    (
        "google_calendar_delete_event",
        GOOGLE_CALENDAR_DELETE_EVENT_SCHEMA,
        handle_google_calendar_delete_event,
        "Delete a Google Calendar event (requires confirmed=true).",
    ),
]


def register_tools(ctx: Any) -> None:
    for name, schema, handler, description in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="google_calendar",
            schema=schema,
            handler=handler,
            description=description,
        )
    logger.debug("google-calendar: registered %d tools", len(_TOOLS))

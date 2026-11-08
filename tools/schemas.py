"""JSON Schemas for Google Calendar tools."""

from __future__ import annotations

__all__ = [
    "GOOGLE_CALENDAR_LIST_EVENTS_SCHEMA",
    "GOOGLE_CALENDAR_CREATE_EVENT_SCHEMA",
    "GOOGLE_CALENDAR_DELETE_EVENT_SCHEMA",
]

GOOGLE_CALENDAR_LIST_EVENTS_SCHEMA = {
    "description": (
        "List Google Calendar events. Times (time_min/time_max) should be ISO 8601 "
        "with timezone (Z or ±HH:MM). Uses the shared google-workspace OAuth token."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "time_min": {
                "type": "string",
                "description": "Lower bound (inclusive) for event start time, ISO 8601 with timezone.",
            },
            "time_max": {
                "type": "string",
                "description": "Upper bound (exclusive) for event start time, ISO 8601 with timezone.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum events to return (1-100). Default 20.",
                "minimum": 1,
                "maximum": 100,
            },
            "query": {
                "type": "string",
                "description": "Free-text search query.",
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID (default: primary or GOOGLE_CALENDAR_ID).",
            },
        },
        "additionalProperties": False,
    },
}

GOOGLE_CALENDAR_CREATE_EVENT_SCHEMA = {
    "description": (
        "Create a Google Calendar event (real event). start/end must be ISO 8601 with "
        "timezone (Z or ±HH:MM). Confirm with the user if targets/timing are ambiguous."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title/summary."},
            "start": {
                "type": "string",
                "description": "Event start as ISO 8601 datetime with timezone (Z or ±HH:MM).",
            },
            "end": {
                "type": "string",
                "description": "Event end as ISO 8601 datetime with timezone (Z or ±HH:MM).",
            },
            "description": {
                "type": "string",
                "description": "Optional event description.",
            },
            "location": {"type": "string", "description": "Optional event location."},
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional attendee email addresses.",
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID (default: primary).",
            },
        },
        "required": ["summary", "start", "end"],
        "additionalProperties": False,
    },
}

GOOGLE_CALENDAR_DELETE_EVENT_SCHEMA = {
    "description": (
        "Delete a Google Calendar event. Destructive action — confirm with the user before calling. "
        "Requires confirmed=true."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "The Google Calendar event ID to delete.",
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID (default: primary).",
            },
            "confirmed": {
                "type": "boolean",
                "description": "Must be true after explicit user confirmation.",
            },
        },
        "required": ["event_id", "confirmed"],
        "additionalProperties": False,
    },
}

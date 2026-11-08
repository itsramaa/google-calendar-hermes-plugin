"""Pydantic v2 models for Google Calendar requests and responses."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

__all__ = ["EventCreateRequest", "EventResponse"]

_TZ_RE = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def _require_tz(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO 8601 datetime string")
    raw = value.strip()
    if "T" not in raw:
        raise ValueError(
            f"{field_name} must be an ISO 8601 datetime with time and timezone (e.g. 2026-05-14T09:00:00Z)"
        )
    if not _TZ_RE.search(raw):
        raise ValueError(
            f"{field_name} must include timezone info (Z or ±HH:MM); naive datetimes are not accepted"
        )
    # Basic parseability check without importing dateutil.
    try:
        from datetime import datetime

        probe = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        datetime.fromisoformat(probe)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"{field_name} is not a parseable ISO 8601 datetime: {raw}"
        ) from exc
    return raw


class EventCreateRequest(BaseModel):
    summary: str = Field(min_length=1)
    start: str
    end: str
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[list[str]] = None
    calendar_id: str = "primary"

    @field_validator("start")
    @classmethod
    def _start_tz(cls, value: str) -> str:
        return _require_tz(value, "start")

    @field_validator("end")
    @classmethod
    def _end_tz(cls, value: str) -> str:
        return _require_tz(value, "end")


class EventResponse(BaseModel):
    id: str = ""
    summary: str = ""
    start: str = ""
    end: str = ""
    status: str = ""
    html_link: str = ""
    hangout_link: str = ""
    location: str = ""
    description: str = ""
    attendees_count: int = 0

    @classmethod
    def from_api(cls, event: dict) -> "EventResponse":
        event = event or {}
        start = event.get("start") or {}
        end = event.get("end") or {}
        attendees = event.get("attendees") or []
        return cls(
            id=event.get("id", "") or "",
            summary=event.get("summary", "") or "",
            start=start.get("dateTime") or start.get("date") or "",
            end=end.get("dateTime") or end.get("date") or "",
            status=event.get("status", "") or "",
            html_link=event.get("htmlLink", "") or "",
            hangout_link=event.get("hangoutLink", "") or "",
            location=event.get("location", "") or "",
            description=event.get("description", "") or "",
            attendees_count=len(attendees) if isinstance(attendees, list) else 0,
        )

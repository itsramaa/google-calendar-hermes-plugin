"""Typed exceptions for the Google Calendar plugin."""

from __future__ import annotations

from typing import Optional

__all__ = [
    "CalendarPluginError",
    "CalendarAuthError",
    "CalendarAPIError",
    "EventNotFoundError",
]


class CalendarPluginError(Exception):
    """Base error for calendar plugin failures."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status: Optional[int] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.hint = hint


class CalendarAuthError(CalendarPluginError):
    """Authentication/authorization failure or missing token."""


class CalendarAPIError(CalendarPluginError):
    """Google Calendar API or transport failure."""


class EventNotFoundError(CalendarPluginError):
    """Requested calendar event was not found."""

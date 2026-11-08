"""Unit tests for the Google Calendar client."""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from google_calendar.config import CalendarConfig
from google_calendar.exceptions import CalendarAuthError
from google_calendar.models import EventCreateRequest


def _run(coro):
    return asyncio.run(coro)


def _fake_service(events: list[Dict[str, Any]]):
    service = MagicMock()
    list_op = MagicMock()
    list_op.execute.return_value = {"items": events, "nextPageToken": None}
    service.events().list.return_value = list_op

    insert_op = MagicMock()
    insert_op.execute.return_value = {
        "id": "new-event-id",
        "summary": "Inserted",
        "start": {"dateTime": "2026-01-01T00:00:00Z"},
        "end": {"dateTime": "2026-01-01T01:00:00Z"},
    }
    service.events().insert.return_value = insert_op
    service.events().delete.return_value.execute.return_value = None
    return service


def test_missing_token_raises_auth_error(tmp_path):
    from google_calendar.client import GoogleCalendarClient

    config = CalendarConfig(
        token_path=tmp_path / "google_token.json",
        client_secret_path=tmp_path / "client_secret.json",
    )
    client = GoogleCalendarClient(config)
    assert not config.has_token
    with pytest.raises(CalendarAuthError):
        client._service()


def test_list_events_maps_responses(config, monkeypatch):
    from google_calendar.client import GoogleCalendarClient

    events = [
        {
            "id": "evt-1",
            "summary": "Standup",
            "start": {"dateTime": "2026-01-01T09:00:00Z"},
            "end": {"dateTime": "2026-01-01T09:15:00Z"},
            "location": "Meeting room",
            "status": "confirmed",
            "htmlLink": "https://calendar.google.com/evt-1",
            "attendees": [{"email": "a@b.com"}, {"email": "c@d.com"}],
        }
    ]
    service = _fake_service(events)
    monkeypatch.setattr(GoogleCalendarClient, "_service", lambda self: service)

    client = GoogleCalendarClient(config)
    result = _run(client.list_events(max_results=5, q="standup"))
    assert result["calendar_id"] == "primary"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == "evt-1"
    assert item["summary"] == "Standup"
    assert item["attendees_count"] == 2
    assert item["location"] == "Meeting room"


def test_create_event_builds_body(config, monkeypatch):
    from google_calendar.client import GoogleCalendarClient

    service = _fake_service([])
    monkeypatch.setattr(GoogleCalendarClient, "_service", lambda self: service)
    client = GoogleCalendarClient(config)

    payload = EventCreateRequest(
        summary="Focus",
        start="2026-02-01T10:00:00Z",
        end="2026-02-01T11:00:00Z",
        description="Deep work",
        location="Desk",
        attendees=["a@b.com"],
    )
    result = _run(client.create_event(payload))
    assert result["id"] == "new-event-id"
    insert_call = service.events().insert.call_args.kwargs
    body = insert_call["body"]
    assert body["summary"] == "Focus"
    assert body["start"]["dateTime"] == "2026-02-01T10:00:00Z"
    assert body["attendees"] == [{"email": "a@b.com"}]


def test_delete_event_returns_shape(config, monkeypatch):
    from google_calendar.client import GoogleCalendarClient

    service = _fake_service([])
    monkeypatch.setattr(GoogleCalendarClient, "_service", lambda self: service)
    client = GoogleCalendarClient(config)
    result = _run(client.delete_event("evt-1"))
    assert result["deleted"] is True
    assert result["event_id"] == "evt-1"


def test_get_status_reports_missing_token(tmp_path):
    from google_calendar.client import GoogleCalendarClient

    config = CalendarConfig(
        token_path=tmp_path / "no-token.json",
        client_secret_path=tmp_path / "client.json",
    )
    client = GoogleCalendarClient(config)
    status = _run(client.get_status())
    assert status["configured"] is False
    assert "token" in status["error"].lower() or "Token" in status["error"]


def test_event_request_rejects_naive_times():
    with pytest.raises(ValueError):
        EventCreateRequest(
            summary="x", start="2026-01-01T09:00:00", end="2026-01-01T10:00:00"
        )


def test_event_request_accepts_z_and_offset():
    a = EventCreateRequest(
        summary="x", start="2026-01-01T09:00:00Z", end="2026-01-01T10:00:00Z"
    )
    assert a.start.endswith("Z")
    b = EventCreateRequest(
        summary="x", start="2026-01-01T09:00:00+07:00", end="2026-01-01T10:00:00+07:00"
    )
    assert b.start.endswith("+07:00")

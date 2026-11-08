"""Unit tests for Google Calendar tool handlers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _load(name: str) -> dict:
    return json.loads(name)


def _fake_client(**overrides):
    client = MagicMock()
    client.list_events = _as_coro({"items": [{"id": "1"}], "calendar_id": "primary"})
    client.create_event = _as_coro({"id": "created"})
    client.delete_event = _as_coro({"deleted": True, "event_id": "evt-1"})
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


def _as_coro(value):
    """Return a callable that produces a fresh coroutine resolving to value."""

    def _call(*_a, **_k):
        async def _inner():
            return value

        return _inner()

    return _call


def test_list_handler_returns_tool_result():
    from google_calendar.tools.handlers import handle_google_calendar_list_events

    client = _fake_client()
    with patch("google_calendar.tools.handlers._client", return_value=client):
        result = json.loads(handle_google_calendar_list_events({"max_results": 10}))
    assert result["ok"] is True
    assert result["data"]["items"][0]["id"] == "1"


def test_create_handler_returns_tool_result():
    from google_calendar.tools.handlers import handle_google_calendar_create_event

    client = _fake_client()
    with patch("google_calendar.tools.handlers._client", return_value=client):
        result = json.loads(
            handle_google_calendar_create_event(
                {
                    "summary": "Test",
                    "start": "2026-01-01T00:00:00Z",
                    "end": "2026-01-01T01:00:00Z",
                }
            )
        )
    assert result["ok"] is True
    assert result["data"]["id"] == "created"


def test_create_handler_validates_timezone():
    from google_calendar.tools.handlers import handle_google_calendar_create_event

    result = json.loads(
        handle_google_calendar_create_event(
            {
                "summary": "Test",
                "start": "2026-01-01T00:00:00",
                "end": "2026-01-01T01:00:00",
            }
        )
    )
    assert result["ok"] is False
    assert result.get("code") == "invalid_input"


def test_delete_requires_confirmation():
    from google_calendar.tools.handlers import handle_google_calendar_delete_event

    result = json.loads(handle_google_calendar_delete_event({"event_id": "evt-1"}))
    assert result["ok"] is False
    assert result.get("requires_confirmation") is True


def test_delete_handler_calls_client_when_confirmed():
    from google_calendar.tools.handlers import handle_google_calendar_delete_event

    client = _fake_client()
    with patch("google_calendar.tools.handlers._client", return_value=client):
        result = json.loads(
            handle_google_calendar_delete_event(
                {"event_id": "evt-1", "confirmed": True}
            )
        )
    assert result["ok"] is True
    assert result["data"]["deleted"] is True


def test_auth_error_shape():
    from google_calendar.exceptions import CalendarAuthError
    from google_calendar.tools.handlers import handle_google_calendar_list_events

    async def _boom(*_a, **_k):
        raise CalendarAuthError("missing token", code="missing_token", hint="run setup")

    client = _fake_client()
    client.list_events = _boom
    with patch("google_calendar.tools.handlers._client", return_value=client):
        result = json.loads(handle_google_calendar_list_events({}))
    assert result["ok"] is False
    assert "setup" in (result.get("hint") or "")

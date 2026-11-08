"""Dashboard API tests for Google Calendar plugin."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _load_router_module():
    plugin_api = PLUGIN_ROOT / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location(
        "google_calendar_plugin_api", plugin_api
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # The plugin_api module is loaded in isolation (no `__package__`), so its
    # Pydantic model forward-reference machinery lacks a proper globalns.
    # Rebuild it after registering the module in sys.modules so types resolve.
    module.CreateEventBody.model_rebuild()
    return module


def _awaitable(value):
    async def _coro():
        return value

    return _coro()


def _awaitable(value):
    async def _coro():
        return value

    return _coro()


@pytest.fixture
def app():
    module = _load_router_module()
    app = FastAPI()
    app.include_router(module.router)
    app.state._gcal_module = module
    return app


@pytest.mark.anyio
async def test_status_endpoint(app):
    module = app.state._gcal_module
    fake_status = {"configured": True, "calendar_id": "primary"}
    with (
        patch.object(module, "_run", return_value=fake_status),
        patch.object(module, "_client", return_value=MagicMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/status")
    assert resp.status_code == 200
    assert resp.json()["configured"] is True


@pytest.mark.anyio
async def test_events_missing_token_returns_error_shape(app, tmp_path):
    module = app.state._gcal_module
    from google_calendar.config import CalendarConfig

    cfg = CalendarConfig(
        token_path=tmp_path / "missing.json", client_secret_path=tmp_path / "c.json"
    )
    with patch.object(module, "CalendarConfig") as cc:
        cc.from_env.return_value = cfg
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/events")
    body = resp.json()
    assert resp.status_code == 200
    assert body["configured"] is False
    assert body["error"]


@pytest.mark.anyio
async def test_create_event_validation_error(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/events", json={"summary": "x", "start": "bad", "end": "bad"}
        )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_create_event_success(app):
    module = app.state._gcal_module
    with (
        patch.object(module, "_run", return_value={"id": "evt-1", "summary": "ok"}),
        patch.object(module, "_client", return_value=MagicMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/events",
                json={
                    "summary": "ok",
                    "start": "2026-01-01T00:00:00Z",
                    "end": "2026-01-01T01:00:00Z",
                },
            )
    assert resp.status_code == 200
    assert resp.json()["id"] == "evt-1"


@pytest.mark.anyio
async def test_delete_event_success(app):
    module = app.state._gcal_module
    with (
        patch.object(
            module, "_run", return_value={"deleted": True, "event_id": "evt-1"}
        ),
        patch.object(module, "_client", return_value=MagicMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.delete("/events/evt-1")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.anyio
async def test_delete_event_not_found_maps_404(app):
    module = app.state._gcal_module
    from google_calendar.exceptions import EventNotFoundError

    def _boom(*_a, **_k):
        raise EventNotFoundError("missing", code="not_found", status=404)

    with (
        patch.object(module, "_run", side_effect=_boom),
        patch.object(module, "_client", return_value=MagicMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.delete("/events/nope")
    assert resp.status_code == 404

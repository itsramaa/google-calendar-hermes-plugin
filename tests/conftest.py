"""Shared fixtures for google-calendar plugin tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_PLUGIN_NAME = "google_calendar"
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

# The plugin dir is named with a hyphen (google-calendar), which is not a
# valid Python identifier. Register it under the alias `google_calendar` so
# `import google_calendar` (and submodules) resolve correctly in tests.
if _PLUGIN_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        _PLUGIN_NAME,
        _PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PLUGIN_NAME] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_token(tmp_path: Path) -> Path:
    """Create a fake authorized_user token file and return the path."""
    token = tmp_path / "google_token.json"
    token.write_text(
        """{
          "type": "authorized_user",
          "client_id": "fake",
          "client_secret": "fake",
          "refresh_token": "fake-refresh",
          "token": "fake-access",
          "scopes": ["https://www.googleapis.com/auth/calendar"]
        }""",
        encoding="utf-8",
    )
    return token


@pytest.fixture
def config(tmp_path: Path, fake_token: Path):
    from google_calendar.config import CalendarConfig

    return CalendarConfig(
        token_path=fake_token,
        client_secret_path=tmp_path / "google_client_secret.json",
        default_calendar_id="primary",
        timeout_seconds=15,
    )

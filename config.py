"""Google Calendar plugin configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

__all__ = ["CalendarConfig", "DEFAULT_TIMEOUT"]

DEFAULT_TIMEOUT = 15


def _hermes_home() -> Path:
    try:
        from hermes_cli._hermes_home import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


@dataclass(frozen=True)
class CalendarConfig:
    token_path: Path
    client_secret_path: Path
    default_calendar_id: str = "primary"
    timeout_seconds: int = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        home = _hermes_home()
        try:
            timeout = int(os.environ.get("GOOGLE_CALENDAR_TIMEOUT", DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        return cls(
            token_path=home / "google_token.json",
            client_secret_path=home / "google_client_secret.json",
            default_calendar_id=os.environ.get("GOOGLE_CALENDAR_ID", "primary")
            or "primary",
            timeout_seconds=max(1, timeout),
        )

    @property
    def has_token(self) -> bool:
        return self.token_path.exists()

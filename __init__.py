"""Google Calendar plugin entry point."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(ctx: Any) -> None:
    """Register google-calendar tools with the plugin context."""
    from .tools import register_tools

    register_tools(ctx)
    logger.debug("google-calendar: registered tools")

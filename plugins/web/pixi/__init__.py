"""Pixi Gateway web search + extract plugin — bundled, auto-loaded."""
from __future__ import annotations
from plugins.web.pixi.provider import PixiGatewayWebSearchProvider


def register(ctx) -> None:
    ctx.register_web_search_provider(PixiGatewayWebSearchProvider())

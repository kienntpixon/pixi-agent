"""Pixi Gateway web search + extract (``/v1/web/search``, ``/v1/web/extract``; sync httpx).

The Pixi backend keeps the search vendor keys (Tavily, Exa, Brave, Jina, Ollama) and
picks one per request; the engine only ever presents the employee's own gateway key,
so every search is attributed to the person who ran it.

No setup of its own. The gateway URL comes from the ``Pixi Gateway`` entry Pixi
writes into ``custom_providers`` at login (its ``base_url`` ends in ``/v1``), the key
from ``PIXI_LLM_KEY`` in the spawn env — the same pair the model provider uses.
``PIXI_WEB_GATEWAY_URL`` overrides the URL (``…/v1/web``) for testing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from plugins.web._common import (
    BaseWebSearchProvider, SEARCH_LIMIT_CAP, document, extract_fail, page_error, provider_env,
    run_extract, run_search, search_fail, search_ok, setup_schema, title_hit,
)

logger = logging.getLogger(__name__)

PIXI_PROVIDER_NAME = "Pixi Gateway"  # backend: httpapi.managedProviderName
KEY_ENV = "PIXI_LLM_KEY"  # backend: httpapi.GatewayKeyEnv
URL_ENV = "PIXI_WEB_GATEWAY_URL"
_EXTRACT_BATCH = 20  # the gateway's per-request URL cap


def gateway_url() -> str:
    """``…/v1/web`` of the Pixi Gateway, or "" when this engine is not logged in to Pixi."""
    explicit = provider_env(URL_ENV).strip()
    if explicit:
        return explicit.rstrip("/")
    try:
        from hermes_cli.config import load_config
        providers = load_config().get("custom_providers") or []
    except Exception:  # noqa: BLE001 — config optional here
        return ""
    for entry in providers if isinstance(providers, list) else []:
        if isinstance(entry, dict) and entry.get("name") == PIXI_PROVIDER_NAME:
            base = str(entry.get("base_url") or "").strip().rstrip("/")
            if base:
                return base + "/web"
    return ""


def gateway_ready() -> bool:
    return bool(gateway_url() and provider_env(KEY_ENV))


def _error_text(response: httpx.Response) -> str:
    """The gateway's own message (``{"error":{"message":…}}``), else the body."""
    try:
        err = response.json().get("error")
        if isinstance(err, dict) and err.get("message"):
            return f"Pixi Gateway: {err['message']} (HTTP {response.status_code})"
    except Exception:  # noqa: BLE001
        pass
    return f"Pixi Gateway returned HTTP {response.status_code}: {(response.text or '').strip()[:300]}"


def _post(endpoint: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    """POST to the gateway; non-2xx raises ValueError with the gateway's message."""
    base, key = gateway_url(), provider_env(KEY_ENV)
    if not base or not key:
        raise ValueError(
            "Pixi Gateway web search is unavailable: sign in to Pixi (no gateway URL or PIXI_LLM_KEY)."
        )
    response = httpx.post(
        f"{base}/{endpoint}", json=payload, timeout=timeout,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    if response.status_code >= 400:
        raise ValueError(_error_text(response))
    return response.json()


class PixiGatewayWebSearchProvider(BaseWebSearchProvider):
    """Search + extract through the Pixi Gateway."""

    NAME = "pixi"
    DISPLAY_NAME = "Pixi Gateway"
    KEY_ENV = KEY_ENV
    EXTRACT = True

    def is_available(self) -> bool:
        return gateway_ready()

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        def _body() -> Dict[str, Any]:
            logger.info("Pixi Gateway search: '%s' (limit=%d)", query, limit)
            data = _post("search", {"query": query, "max_results": max(1, min(int(limit), SEARCH_LIMIT_CAP))}, 40)
            return search_ok([
                title_hit(r.get("title", ""), r.get("url", ""), r.get("content", ""), i + 1)
                for i, r in enumerate(data.get("results") or [])
            ])

        return run_search("Pixi Gateway", logger, _body)

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        def _body() -> List[Dict[str, Any]]:
            logger.info("Pixi Gateway extract: %d URL(s)", len(urls))
            out: List[Dict[str, Any]] = []
            for i in range(0, len(urls), _EXTRACT_BATCH):
                batch = urls[i:i + _EXTRACT_BATCH]
                try:
                    data = _post("extract", {"urls": batch}, 120)
                except ValueError as exc:
                    out += extract_fail(batch, str(exc))
                    continue
                out += [
                    document(r.get("url", ""), r.get("title", ""), r.get("raw_content", "") or "")
                    for r in data.get("results") or []
                ]
                out += [page_error(f.get("url", ""), f.get("error", "extraction failed")) for f in data.get("failed_results") or []]
            return out

        return run_extract("Pixi Gateway", logger, urls, _body)

    def get_setup_schema(self) -> Dict[str, Any]:
        return setup_schema(
            "Pixi Gateway", "pixi · no key", "Search + extract through your Pixi login. Nothing to configure.",
        )

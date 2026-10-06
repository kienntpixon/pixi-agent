"""Tests for the Pixi Gateway web provider (plugins/web/pixi).

The provider has no settings of its own: it is available exactly when the engine is
signed in to Pixi (a ``Pixi Gateway`` entry in ``custom_providers`` plus
``PIXI_LLM_KEY``), and then leads backend autodetection so searches go through the
company gateway unless the user has picked a backend explicitly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

GATEWAY_CFG = {"custom_providers": [
    {"name": "Someone else", "base_url": "https://other.example/v1"},
    {"name": "Pixi Gateway", "base_url": "https://pixi.example/v1/", "api_key": "${PIXI_LLM_KEY}"},
]}


@pytest.fixture
def signed_in(monkeypatch):
    monkeypatch.setenv("PIXI_LLM_KEY", "pixi_llm_test")
    monkeypatch.delenv("PIXI_WEB_GATEWAY_URL", raising=False)
    with patch("hermes_cli.config.load_config", return_value=GATEWAY_CFG):
        yield


def _resp(status, payload):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = str(payload)
    return r


class TestAvailability:
    def test_url_comes_from_the_pixi_gateway_provider(self, signed_in):
        from plugins.web.pixi.provider import PixiGatewayWebSearchProvider, gateway_url
        assert gateway_url() == "https://pixi.example/v1/web"
        assert PixiGatewayWebSearchProvider().is_available() is True

    def test_unavailable_without_key(self, signed_in, monkeypatch):
        monkeypatch.delenv("PIXI_LLM_KEY")
        with patch("agent.web_search_provider.get_provider_env", return_value=""):
            from plugins.web.pixi.provider import PixiGatewayWebSearchProvider
            assert PixiGatewayWebSearchProvider().is_available() is False

    def test_unavailable_when_not_signed_in(self, monkeypatch):
        monkeypatch.setenv("PIXI_LLM_KEY", "pixi_llm_test")
        monkeypatch.delenv("PIXI_WEB_GATEWAY_URL", raising=False)
        with patch("hermes_cli.config.load_config", return_value={}):
            from plugins.web.pixi.provider import PixiGatewayWebSearchProvider
            assert PixiGatewayWebSearchProvider().is_available() is False

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PIXI_WEB_GATEWAY_URL", "http://localhost:8090/v1/web/")
        from plugins.web.pixi.provider import gateway_url
        assert gateway_url() == "http://localhost:8090/v1/web"


class TestSearchAndExtract:
    def test_search_posts_with_the_employee_key(self, signed_in):
        from plugins.web.pixi.provider import PixiGatewayWebSearchProvider
        payload = {"results": [{"title": "A", "url": "https://a", "content": "snip"}], "provider": "tavily"}
        with patch("plugins.web.pixi.provider.httpx.post", return_value=_resp(200, payload)) as post:
            out = PixiGatewayWebSearchProvider().search("pixi", limit=50)
        assert out == {"success": True, "data": {"web": [
            {"title": "A", "url": "https://a", "description": "snip", "position": 1}]}}
        args, kwargs = post.call_args
        assert args[0] == "https://pixi.example/v1/web/search"
        assert kwargs["headers"]["Authorization"] == "Bearer pixi_llm_test"
        assert kwargs["json"] == {"query": "pixi", "max_results": 20}

    def test_search_surfaces_the_gateway_message(self, signed_in):
        from plugins.web.pixi.provider import PixiGatewayWebSearchProvider
        err = {"error": {"message": "no web search provider is configured on the Pixi Gateway"}}
        with patch("plugins.web.pixi.provider.httpx.post", return_value=_resp(503, err)):
            out = PixiGatewayWebSearchProvider().search("pixi")
        assert out["success"] is False
        assert "no web search provider is configured" in out["error"]

    def test_extract_maps_results_and_failures(self, signed_in):
        from plugins.web.pixi.provider import PixiGatewayWebSearchProvider
        payload = {"results": [{"url": "https://a", "title": "A", "raw_content": "# A"}],
                   "failed_results": [{"url": "https://b", "error": "timeout"}]}
        with patch("plugins.web.pixi.provider.httpx.post", return_value=_resp(200, payload)):
            docs = PixiGatewayWebSearchProvider().extract(["https://a", "https://b"])
        assert docs[0]["url"] == "https://a" and docs[0]["content"] == "# A"
        assert docs[1] == {"url": "https://b", "title": "", "content": "", "error": "timeout"}


class TestAutodetect:
    def test_pixi_leads_when_nothing_is_configured(self, signed_in, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-own")
        import tools.web_tools as wt
        with patch.object(wt, "_load_web_config", return_value={}), \
             patch.object(wt, "selection_exists", return_value=False):
            assert wt._get_backend() == "pixi"

    def test_explicit_user_choice_wins(self, signed_in):
        import tools.web_tools as wt
        with patch.object(wt, "_load_web_config", return_value={"backend": "tavily"}):
            assert wt._get_backend() == "tavily"

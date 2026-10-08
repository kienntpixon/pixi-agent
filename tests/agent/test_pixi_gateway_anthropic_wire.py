"""Pixi LLM gateway ``/v1/messages`` takes the native Anthropic path for wire features.

The gateway forwards bodies verbatim to the Claude API with per-user sticky keys, so
thinking signatures, prompt-cache markers and fast mode behave as native. Only the
operator-set ``PIXI_LLM_ANTHROPIC_BASE_URL`` host qualifies; auth stays x-api-key.
"""

from __future__ import annotations

import pytest

from agent.anthropic_endpoints import _is_pixi_gateway_endpoint

GATEWAY_URL = "https://llm.pixi.test"
MODEL = "pixi-claude-opus-4-8"
ENV = "PIXI_LLM_ANTHROPIC_BASE_URL"


@pytest.fixture
def gateway_env(monkeypatch):
    monkeypatch.setenv(ENV, GATEWAY_URL)


def _messages():
    return [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant", "content": "calling",
            "tool_calls": [{"id": "t1", "type": "function",
                            "function": {"name": "terminal", "arguments": '{"cmd":"ls"}'}}],
            "anthropic_content_blocks": [
                {"type": "thinking", "thinking": "plan", "signature": "sig-pixi"},
                {"type": "text", "text": "calling"},
                {"type": "tool_use", "id": "t1", "name": "terminal", "input": {"cmd": "ls"}},
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "name": "terminal", "content": "done"},
    ]


def _latest_thinking(base_url):
    from agent.anthropic_message_convert import convert_messages_to_anthropic

    _system, converted = convert_messages_to_anthropic(_messages(), base_url=base_url, model=MODEL)
    assistant = [m for m in converted if m["role"] == "assistant"][-1]
    return [b for b in assistant["content"] if isinstance(b, dict) and b.get("type") == "thinking"]


class TestPredicate:
    def test_unset_env_never_matches(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        assert not _is_pixi_gateway_endpoint(GATEWAY_URL)
        monkeypatch.setenv(ENV, "  ")
        assert not _is_pixi_gateway_endpoint(GATEWAY_URL)

    def test_exact_host_matches_regardless_of_path(self, gateway_env):
        assert _is_pixi_gateway_endpoint(GATEWAY_URL)
        assert _is_pixi_gateway_endpoint("https://LLM.pixi.test/v1/")

    @pytest.mark.parametrize("url", [
        "https://llm.pixi.test.attacker.test",   # lookalike suffix
        "https://evil.llm.pixi.test",            # sibling/subdomain
        "https://attacker.test/llm.pixi.test",   # path spoof
        "",
        None,
    ])
    def test_lookalikes_do_not_match(self, gateway_env, url):
        assert not _is_pixi_gateway_endpoint(url)

    def test_port_is_compared_when_the_env_sets_one(self, monkeypatch):
        monkeypatch.setenv(ENV, "https://llm.pixi.test:8443")
        assert _is_pixi_gateway_endpoint("https://llm.pixi.test:8443/v1")
        assert not _is_pixi_gateway_endpoint("https://llm.pixi.test")
        assert not _is_pixi_gateway_endpoint("https://llm.pixi.test:9443")


class TestThinkingReplay:
    def test_gateway_keeps_signed_thinking_on_latest_turn(self, gateway_env):
        thinking = _latest_thinking(GATEWAY_URL)
        assert [b.get("signature") for b in thinking] == ["sig-pixi"]

    def test_without_env_the_host_is_plain_third_party(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        assert _latest_thinking(GATEWAY_URL) == []


class TestAdapter:
    def _kwargs(self, base_url):
        from agent.anthropic_adapter import build_anthropic_kwargs

        return build_anthropic_kwargs(
            model=MODEL, messages=[{"role": "user", "content": "hi"}], tools=None,
            max_tokens=1024, reasoning_config=None, base_url=base_url, fast_mode=True,
        )

    def test_fast_mode_reaches_the_gateway(self, gateway_env):
        assert self._kwargs(GATEWAY_URL).get("extra_body", {}).get("speed") == "fast"

    def test_fast_mode_stays_off_for_unconfigured_hosts(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        assert "speed" not in self._kwargs(GATEWAY_URL).get("extra_body", {})

    def test_gateway_key_still_sent_as_x_api_key(self, gateway_env):
        """No Bearer, and no OAuth detection even for an OAuth-shaped key."""
        from agent.anthropic_adapter import _auth_style
        from agent.anthropic_credentials import _is_oauth_token

        key = "sk-ant-oat01-looks-like-oauth"
        assert _is_oauth_token(key)
        assert _auth_style(key, GATEWAY_URL, GATEWAY_URL) == "api_key"


class TestPromptCachePolicy:
    def _agent(self):
        from unittest.mock import MagicMock
        from run_agent import AIAgent

        agent = AIAgent.__new__(AIAgent)
        agent.provider, agent.base_url, agent.api_mode, agent.model = (
            "custom", GATEWAY_URL, "anthropic_messages", MODEL)
        agent._base_url_lower = GATEWAY_URL
        agent._custom_providers = []
        agent.client = MagicMock()
        agent.quiet_mode = True
        return agent

    def test_gateway_gets_native_layout_and_tool_markers(self, gateway_env):
        agent = self._agent()
        assert agent._anthropic_prompt_cache_policy() == (True, True)
        assert agent._direct_native_anthropic_tool_cache_capability() is True
        assert agent._direct_native_anthropic_tool_cache_capability(api_mode="chat_completions") is False

    def test_without_env_no_tool_markers(self, monkeypatch):
        monkeypatch.delenv(ENV, raising=False)
        assert self._agent()._direct_native_anthropic_tool_cache_capability() is False

"""
Tests for src/core/proposal_executor.py

Covers the execution logic that runs AFTER a proposal is approved —
specifically the _execute_llm_switch path, which had a bug where
claude_path and save_as_default were silently dropped.

These tests exist because the approval flow in test_api.py only tests
the HTTP layer (approve endpoint returns 200) — it does NOT verify
what the executor actually did with the proposal payload.
"""

import os
import tempfile
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from src.core.proposal_store import get_proposal_store, RiskClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_switch_proposal(payload: dict):
    """Create a pending llm_switch proposal in a fresh store."""
    store = get_proposal_store()
    return store.create(
        action_type="llm_switch",
        risk_class=RiskClass.EPHEMERAL,
        reversible=True,
        proposed_by="test",
        description="test switch",
        payload=payload,
    )


# Providers are lazy-imported inside _execute_llm_switch, so patch at source.
_GW   = "src.core.llm_gateway.LLMGateway"
_CC   = "src.core.llm_gateway.ClaudeCodeCLIProvider"
_GEM  = "src.core.llm_gateway.GeminiCLIProvider"
_OLL  = "src.core.llm_gateway.OllamaProvider"


# ---------------------------------------------------------------------------
# Payload forwarding
# ---------------------------------------------------------------------------

class TestExecuteLLMSwitch:

    @pytest.mark.asyncio
    async def test_claude_path_forwarded_to_provider(self):
        """
        Regression: claude_path in payload must reach ClaudeCodeCLIProvider.
        Bug: payload["claude_path"] was never written into llm_cfg, so the
             custom path was silently ignored and auto-detection ran instead.
        """
        custom_path = r"C:\Users\test\.local\bin\claude.exe"
        proposal = _make_llm_switch_proposal({
            "provider":        "claude-code",
            "model":           "claude-sonnet-4-6",
            "claude_path":     custom_path,
            "save_as_default": False,
        })

        captured = {}

        def fake_cc(cfg):
            captured.update(cfg)
            return MagicMock()

        with patch(_CC, side_effect=fake_cc), patch(_GW, return_value=MagicMock()):
            from src.core.proposal_executor import _execute_llm_switch
            await _execute_llm_switch(proposal)

        assert captured.get("claude_path") == custom_path, (
            f"claude_path not forwarded. Captured cfg: {captured}"
        )

    @pytest.mark.asyncio
    async def test_model_forwarded_to_claude_code_provider(self):
        """req_model must be written into llm_cfg['claude_model']."""
        proposal = _make_llm_switch_proposal({
            "provider": "claude-code", "model": "claude-opus-4-6",
            "claude_path": None, "save_as_default": False,
        })
        captured = {}
        with patch(_CC, side_effect=lambda cfg: (captured.update(cfg), MagicMock())[1]), \
             patch(_GW, return_value=MagicMock()):
            from src.core.proposal_executor import _execute_llm_switch
            await _execute_llm_switch(proposal)
        assert captured.get("claude_model") == "claude-opus-4-6"

    @pytest.mark.asyncio
    async def test_no_claude_path_key_when_payload_is_none(self):
        """claude_path must NOT appear in cfg when payload value is None —
        auto-detection inside ClaudeCodeCLIProvider must run instead."""
        proposal = _make_llm_switch_proposal({
            "provider": "claude-code", "model": "claude-sonnet-4-6",
            "claude_path": None, "save_as_default": False,
        })
        captured = {}
        with patch(_CC, side_effect=lambda cfg: (captured.update(cfg), MagicMock())[1]), \
             patch(_GW, return_value=MagicMock()):
            from src.core.proposal_executor import _execute_llm_switch
            await _execute_llm_switch(proposal)
        assert "claude_path" not in captured

    @pytest.mark.asyncio
    async def test_gemini_model_forwarded(self):
        proposal = _make_llm_switch_proposal({
            "provider": "gemini", "model": "gemini-2.5-pro", "save_as_default": False,
        })
        captured = {}
        with patch(_GEM, side_effect=lambda cfg: (captured.update(cfg), MagicMock())[1]), \
             patch(_GW, return_value=MagicMock()):
            from src.core.proposal_executor import _execute_llm_switch
            await _execute_llm_switch(proposal)
        assert captured.get("gemini_model") == "gemini-2.5-pro"

    @pytest.mark.asyncio
    async def test_ollama_model_forwarded(self):
        proposal = _make_llm_switch_proposal({
            "provider": "ollama", "model": "llama3.2", "save_as_default": False,
        })
        captured = {}
        with patch(_OLL, side_effect=lambda cfg: (captured.update(cfg), MagicMock())[1]), \
             patch(_GW, return_value=MagicMock()):
            from src.core.proposal_executor import _execute_llm_switch
            await _execute_llm_switch(proposal)
        assert captured.get("ollama_model") == "llama3.2"

    @pytest.mark.asyncio
    async def test_result_contains_provider_and_name(self):
        """Return value must have 'provider' and 'provider_name' keys."""
        proposal = _make_llm_switch_proposal({
            "provider": "claude-code", "model": "claude-sonnet-4-6",
            "claude_path": None, "save_as_default": False,
        })
        gw_mock = MagicMock()
        gw_mock.get_provider_name.return_value = "ClaudeCodeCLI (claude-sonnet-4-6)"
        with patch(_CC, return_value=MagicMock()), patch(_GW, return_value=gw_mock):
            from src.core.proposal_executor import _execute_llm_switch
            result = await _execute_llm_switch(proposal)
        assert result["provider"] == "claude-code"
        assert "provider_name" in result


# ---------------------------------------------------------------------------
# save_as_default — config.yaml persistence
# ---------------------------------------------------------------------------

class TestSaveAsDefault:

    def _real_config_path(self):
        """Compute the same config path the executor uses."""
        executor_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "core", "proposal_executor.py",
        )
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(executor_file)))),
            "config", "config.yaml",
        )

    @pytest.mark.asyncio
    async def test_save_as_default_updates_provider_in_config(self):
        """When save_as_default=True, the provider line in config.yaml is updated."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "config.yaml",
        )
        # Back up original
        with open(config_path) as f:
            original = f.read()

        try:
            proposal = _make_llm_switch_proposal({
                "provider": "claude-code", "model": "claude-sonnet-4-6",
                "claude_path": None, "save_as_default": True,
            })
            with patch(_CC, return_value=MagicMock()), patch(_GW, return_value=MagicMock()):
                from src.core.proposal_executor import _execute_llm_switch
                result = await _execute_llm_switch(proposal)

            with open(config_path) as f:
                saved = f.read()

            assert 'provider: "claude-code"' in saved, (
                f"config.yaml not updated. Content:\n{saved}"
            )
            assert result.get("saved_as_default") is True
        finally:
            with open(config_path, "w") as f:
                f.write(original)

    @pytest.mark.asyncio
    async def test_save_as_default_false_leaves_config_unchanged(self):
        """When save_as_default=False, config.yaml must not be written."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "config.yaml",
        )
        with open(config_path) as f:
            original = f.read()

        try:
            proposal = _make_llm_switch_proposal({
                "provider": "ollama", "model": "llama3.2",
                "save_as_default": False,
            })
            with patch(_OLL, return_value=MagicMock()), patch(_GW, return_value=MagicMock()):
                from src.core.proposal_executor import _execute_llm_switch
                await _execute_llm_switch(proposal)

            with open(config_path) as f:
                after = f.read()

            assert after == original, "config.yaml was modified despite save_as_default=False"
        finally:
            with open(config_path, "w") as f:
                f.write(original)

    @pytest.mark.asyncio
    async def test_save_as_default_updates_model_line(self):
        """save_as_default=True with a claude model must update claude_model in config."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "config.yaml",
        )
        with open(config_path) as f:
            original = f.read()

        try:
            proposal = _make_llm_switch_proposal({
                "provider": "claude-code", "model": "claude-opus-4-6",
                "claude_path": None, "save_as_default": True,
            })
            with patch(_CC, return_value=MagicMock()), patch(_GW, return_value=MagicMock()):
                from src.core.proposal_executor import _execute_llm_switch
                await _execute_llm_switch(proposal)

            with open(config_path) as f:
                saved = f.read()

            assert 'claude_model: "claude-opus-4-6"' in saved, (
                f"claude_model not updated in config. Content:\n{saved}"
            )
        finally:
            with open(config_path, "w") as f:
                f.write(original)

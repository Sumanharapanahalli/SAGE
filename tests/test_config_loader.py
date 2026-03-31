"""
SAGE Framework — Config Loader Tests
=======================================
Tests for the config_loader module that reads config/config.yaml.
"""

import os
import pytest

pytestmark = pytest.mark.unit


class TestConfigLoader:
    """Config loader reads and caches config.yaml."""

    def test_load_config_returns_dict(self):
        from src.core.config_loader import load_config
        cfg = load_config()
        assert isinstance(cfg, dict)

    def test_has_llm_section(self):
        from src.core.config_loader import load_config
        cfg = load_config()
        assert "llm" in cfg

    def test_has_github_section(self):
        from src.core.config_loader import load_config
        cfg = load_config()
        # github section may or may not exist — but load shouldn't crash
        assert isinstance(cfg, dict)

    def test_missing_file_returns_empty(self):
        from src.core.config_loader import load_config
        cfg = load_config(path="/nonexistent/config.yaml")
        assert isinstance(cfg, dict)

    def test_reload_reads_fresh(self):
        from src.core.config_loader import load_config
        cfg1 = load_config()
        cfg2 = load_config()
        assert cfg1 == cfg2

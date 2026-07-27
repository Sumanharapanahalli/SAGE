"""Tests for src.interface.teams_bot config loading + construction.

Previously untested (SAGE self-improvement loop, issue #23).
"""

from unittest.mock import patch

from src.interface.teams_bot import TeamsBot, _load_config


def test_load_config_returns_empty_dict_when_absent():
    with patch("os.path.exists", return_value=False):
        assert _load_config() == {}


def test_load_config_always_returns_dict():
    assert isinstance(_load_config(), dict)


def test_teams_bot_constructs():
    bot = TeamsBot()
    assert bot is not None
    assert hasattr(bot, "logger")

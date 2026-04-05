"""Tests for the connector framework base and registry."""
import pytest

from src.connectors.base import BaseConnector, ConnectorRegistry


class StubConnector(BaseConnector):
    """Test connector that returns canned data."""
    connector_type = "stub"

    def connect(self, config: dict) -> bool:
        self._connected = config.get("valid", True)
        return self._connected

    def fetch(self, **kwargs) -> list[dict]:
        if not self._connected:
            return []
        return [{"id": "1", "content": "stub data"}]

    def sync(self) -> dict:
        items = self.fetch()
        return {"synced": len(items)}


class TestBaseConnector:
    def test_connect_returns_bool(self):
        c = StubConnector()
        assert c.connect({"valid": True}) is True
        assert c.connect({"valid": False}) is False

    def test_fetch_returns_list(self):
        c = StubConnector()
        c.connect({"valid": True})
        result = c.fetch()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_sync_returns_dict(self):
        c = StubConnector()
        c.connect({"valid": True})
        result = c.sync()
        assert result == {"synced": 1}


class TestConnectorRegistry:
    def test_register_and_list(self):
        reg = ConnectorRegistry()
        reg.register("stub", StubConnector)
        types = reg.list_types()
        assert "stub" in types

    def test_create_connector(self):
        reg = ConnectorRegistry()
        reg.register("stub", StubConnector)
        c = reg.create("stub")
        assert isinstance(c, StubConnector)

    def test_create_unknown_raises(self):
        reg = ConnectorRegistry()
        with pytest.raises(KeyError):
            reg.create("unknown")

    def test_register_replaces(self):
        reg = ConnectorRegistry()
        reg.register("stub", StubConnector)
        reg.register("stub", StubConnector)  # should not raise
        assert len(reg.list_types()) == 1

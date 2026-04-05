"""
Connector Framework — Base Classes
====================================

Pluggable connectors for external data sources. Each connector implements
connect(), fetch(), and sync() to bring external data into SAGE's knowledge base.
"""

import logging
from abc import ABC, abstractmethod
from typing import Type

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    connector_type: str = "base"

    def __init__(self):
        self._connected = False
        self._config: dict = {}

    @abstractmethod
    def connect(self, config: dict) -> bool:
        """Establish connection to the data source. Returns True on success."""
        ...

    @abstractmethod
    def fetch(self, **kwargs) -> list[dict]:
        """Fetch data items from the source."""
        ...

    @abstractmethod
    def sync(self) -> dict:
        """Sync data into SAGE knowledge base. Returns summary dict."""
        ...


class ConnectorRegistry:
    """Registry of available connector types."""

    def __init__(self):
        self._types: dict[str, Type[BaseConnector]] = {}

    def register(self, name: str, cls: Type[BaseConnector]):
        self._types[name] = cls
        logger.info("Registered connector: %s", name)

    def list_types(self) -> list[str]:
        return list(self._types.keys())

    def create(self, name: str) -> BaseConnector:
        if name not in self._types:
            raise KeyError(f"Unknown connector type: {name}")
        return self._types[name]()

    def get_info(self) -> list[dict]:
        return [
            {"type": name, "class": cls.__name__, "doc": (cls.__doc__ or "").strip().split("\n")[0]}
            for name, cls in self._types.items()
        ]

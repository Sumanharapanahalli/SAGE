from src.connectors.base import ConnectorRegistry

# Global registry — connectors register here on import
connector_registry = ConnectorRegistry()


def _register_builtins():
    """Register built-in connectors."""
    from src.connectors.filesystem_connector import FilesystemConnector
    from src.connectors.github_connector import GitHubConnector

    connector_registry.register("filesystem", FilesystemConnector)
    connector_registry.register("github", GitHubConnector)


try:
    _register_builtins()
except Exception:
    pass  # connectors may fail to import if deps missing

"""
SAGE Framework — Config Loader
================================
Reads and caches config/config.yaml.

Thread-safe. Returns empty dict on missing file.
"""

import logging
import os

import yaml

logger = logging.getLogger("ConfigLoader")

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "config.yaml",
)


def load_config(path: str = "") -> dict:
    """
    Load configuration from a YAML file.

    Args:
        path: Path to the YAML file. Defaults to config/config.yaml.

    Returns:
        Configuration dict, or empty dict if file missing/invalid.
    """
    filepath = path or _DEFAULT_PATH
    try:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        logger.debug("Config file not found: %s", filepath)
        return {}
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s", filepath, exc)
        return {}
    except Exception as exc:
        logger.warning("Failed to load config %s: %s", filepath, exc)
        return {}

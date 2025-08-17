"""Configuration management for DS2 Cloud Sync."""

import json
from pathlib import Path

from .utils import app_home


CONFIG_FILE = app_home() / "config.json"


def load_config() -> dict:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    """Save configuration to JSON file."""
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
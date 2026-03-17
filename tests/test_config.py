"""Tests for TOML config load/save."""

import tempfile
from pathlib import Path

import pytest

from src.config import DEFAULT_CONFIG, load_config, save_config


def test_save_and_load_roundtrip():
    """Saved config can be loaded and matches (with defaults applied)."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        path = Path(f.name)
    try:
        save_config(path, DEFAULT_CONFIG)
        loaded = load_config(path)
        assert loaded["formats"] == DEFAULT_CONFIG["formats"]
        assert loaded["name_format"] == DEFAULT_CONFIG["name_format"]
        assert loaded["output_dirs"] == DEFAULT_CONFIG["output_dirs"]
        assert loaded["no_lookup"] is False
        assert loaded["verify_accuraterip"] is True
    finally:
        path.unlink(missing_ok=True)


def test_load_missing_file_raises():
    """Loading a missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        load_config(Path("nonexistent.toml"))

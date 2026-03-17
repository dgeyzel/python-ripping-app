"""Tests for CLI entrypoint and help."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_app_rip_help():
    """rip command shows help with options."""
    result = runner.invoke(app, ["rip", "--help"])
    assert result.exit_code == 0
    assert "rip" in result.output
    assert "--format" in result.output or "-f" in result.output
    assert "AccurateRip" in result.output or "accuraterip" in result.output.lower()
    assert "--bitrate" in result.output or "-b" in result.output


def test_app_rip_unsupported_bitrate_shows_list():
    """rip with unsupported bitrate exits with 1 and shows supported bitrates."""
    result = runner.invoke(
        app,
        ["rip", "-f", "flac", "--bitrate", "flac:99", "--no-lookup"],
    )
    assert result.exit_code == 1
    # If we reached bitrate validation (audiotools installed), check message
    if "Unsupported bitrate" in result.output:
        assert "99" in result.output
        assert "flac" in result.output.lower()
        assert "Supported bitrates" in result.output
        assert "0" in result.output and "8" in result.output
    # Otherwise audiotools may be missing and we get a different error


def test_app_list_help():
    """list command shows help."""
    result = runner.invoke(app, ["list", "--help"])
    assert result.exit_code == 0
    assert "device" in result.output or "--device" in result.output


def test_app_rip_with_invalid_device_exits_with_error():
    """rip with nonexistent CUE exits with error (no audiotools required)."""
    result = runner.invoke(
        app, ["rip", "-f", "flac", "--no-lookup", "-d", "nonexistent.cue"]
    )
    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower() or "CUE" in result.output


def test_app_list_with_invalid_device_exits_with_error():
    """list with nonexistent CUE exits with error."""
    result = runner.invoke(app, ["list", "-d", "nonexistent.cue"])
    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower()


def test_config_export_writes_toml():
    """config export creates a TOML file with expected keys."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "settings.toml"
        result = runner.invoke(app, ["config", "export", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        from src.config import load_config

        cfg = load_config(out)
        assert "formats" in cfg
        assert "name_format" in cfg
        assert "output_dirs" in cfg


def test_config_import_valid_file():
    """config import validates a TOML file and suggests rip --config."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "settings.toml"
        runner.invoke(app, ["config", "export", "-o", str(out)])
        result = runner.invoke(app, ["config", "import", str(out)])
        assert result.exit_code == 0
        assert "Valid config" in result.output
        assert "rip --config" in result.output


def test_config_import_missing_file_exits_with_error():
    """config import with missing file exits with 1."""
    result = runner.invoke(app, ["config", "import", "nonexistent.toml"])
    assert result.exit_code == 1
    assert "not found" in result.output or "Error" in result.output

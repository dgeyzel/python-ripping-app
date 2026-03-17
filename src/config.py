"""Load and save rip settings to/from TOML config files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

# Default config values (used when keys are missing on import).
DEFAULT_CONFIG: dict[str, Any] = {
    "formats": ["flac"],
    "device": "",
    "name_format": "%(track_number)2.2d - %(track_name)s",
    "folder_format": "%(album_name)s",
    "no_lookup": False,
    "no_interactive": False,
    "verify_accuraterip": True,
    "output_dirs": {"flac": "."},
    "quality": {"flac": "5"},
    "bitrate": {},
}


def _toml_compatible_dict(config: dict[str, Any]) -> dict[str, Any]:
    """Return a dict with only TOML-serializable values (no None for tables)."""
    out: dict[str, Any] = {}
    for key, value in config.items():
        if key in ("output_dirs", "quality", "bitrate"):
            out[key] = {k: str(v) for k, v in (value or {}).items()}
        elif key == "formats":
            out[key] = list(value) if value else ["flac"]
        elif isinstance(value, bool):
            out[key] = value
        else:
            out[key] = str(value) if value is not None else ""
    return out


def load_config(path: str | Path) -> dict[str, Any]:
    """Load config from a TOML file. Missing keys are filled from defaults."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Normalize: only known keys, merge with defaults
    result = dict(DEFAULT_CONFIG)
    for key in result:
        if key in data:
            val = data[key]
            if key == "output_dirs" and isinstance(val, dict):
                result["output_dirs"] = {str(k): str(v) for k, v in val.items()}
            elif key == "quality" and isinstance(val, dict):
                result["quality"] = {str(k): str(v) for k, v in val.items()}
            elif key == "bitrate" and isinstance(val, dict):
                result["bitrate"] = {str(k): str(v) for k, v in val.items()}
            elif key == "formats" and isinstance(val, list):
                result["formats"] = [str(x).lower() for x in val]
            elif (
                key in ("no_lookup", "no_interactive", "verify_accuraterip")
                and isinstance(val, bool)
            ):
                result[key] = val
            elif key in ("device", "name_format", "folder_format"):
                result[key] = str(val) if val is not None else ""

    return result


def save_config(path: str | Path, config: dict[str, Any]) -> None:
    """Write config to a TOML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _toml_compatible_dict(config)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)

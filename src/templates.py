"""Filename and folder path templates with metadata placeholders and sanitization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# Characters unsafe in filenames on Windows and Linux
_UNSAFE_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_path_part(text: str) -> str:
    """Replace or remove characters unsafe in path segments."""
    if not text or not isinstance(text, str):
        return "Unknown"
    s = _UNSAFE_FS_CHARS.sub("", str(text).strip())
    s = re.sub(r"\s+", " ", s).strip()
    return s or "Unknown"


def format_filename(
    name_format: str,
    metadata: Any,
    suffix: str,
    file_path_fallback: str = "track",
) -> str:
    """Build a filename from a template and metadata (%% placeholders)."""
    out = name_format
    for attr in ("track_number", "track_name", "artist_name", "album_name", "year"):
        val = getattr(metadata, attr, None)
        if val is not None:
            if attr == "track_number":
                out = out.replace("%(track_number)2.2d", f"{int(val):02d}")
                out = out.replace("%(track_number)s", str(val))
            else:
                out = out.replace(f"%({attr})s", str(val))
    out = out.replace("%(suffix)s", suffix)
    out = sanitize_path_part(out) or "track"
    if not out.endswith("." + suffix):
        out = f"{out}.{suffix}"
    return out


def format_folder(
    folder_format: str,
    metadata: Any,
) -> str:
    """Build a folder path string from template and metadata; each segment sanitized."""
    if not folder_format:
        return ""
    raw = folder_format
    for attr in ("year", "artist_name", "album_name", "track_number", "track_name"):
        val = getattr(metadata, attr, None)
        if val is not None:
            raw = raw.replace(f"%({attr})s", str(val))
        if attr == "track_number" and val is not None:
            try:
                raw = raw.replace("%(track_number)2.2d", f"{int(val):02d}")
            except (TypeError, ValueError):
                raw = raw.replace("%(track_number)2.2d", str(val))
    parts = re.split(r"[/\\]+", raw.strip())
    return str(Path(*[sanitize_path_part(p) for p in parts if p]))


def build_track_filename(
    name_format: str,
    metadata: Any,
    suffix: str,
) -> str:
    """Return a safe filename for one track (no directory)."""
    return format_filename(name_format, metadata, suffix)


def build_track_dir_and_filename(
    base_dir: str,
    folder_format: str,
    name_format: str,
    metadata: Any,
    suffix: str,
) -> tuple[Path, str]:
    """Return (full_dir_path, filename) for one track."""
    base = Path(base_dir)
    folder = format_folder(folder_format, metadata)
    if folder:
        full_dir = base / folder
    else:
        full_dir = base
    filename = build_track_filename(name_format, metadata, suffix)
    return full_dir, filename

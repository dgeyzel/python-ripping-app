"""Shared metadata type for track/album info (replaces audiotools.MetaData)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MetaData:
    """Track/album metadata compatible with template placeholders and tagging."""

    track_number: int = 1
    track_total: int = 1
    track_name: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    performer_name: str | None = None
    year: str | None = None

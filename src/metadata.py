"""Metadata lookup via MusicBrainz and FreeDB with interactive match selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from audiotools.cdio import CDDAReader

try:
    import audiotools
    from audiotools import musicbrainz
    from audiotools import freedb
except ImportError:
    audiotools = None  # type: ignore[misc, assignment]
    musicbrainz = None  # type: ignore[misc, assignment]
    freedb = None  # type: ignore[misc, assignment]


# Default MusicBrainz and FreeDB servers (audiotools typically uses these)
MUSICBRAINZ_SERVER = "musicbrainz.org"
MUSICBRAINZ_PORT = 80
FREEDB_SERVER = "gnudb.gnudb.org"
FREEDB_PORT = 80


def _collect_musicbrainz_matches(reader: CDDAReader) -> list[list[Any]]:
    """Return list of metadata matches from MusicBrainz (each match is list of MetaData)."""
    if musicbrainz is None:
        return []
    try:
        disc_id = musicbrainz.DiscID.from_cddareader(reader)
        matches = list(musicbrainz.perform_lookup(disc_id, MUSICBRAINZ_SERVER, MUSICBRAINZ_PORT))
        return matches
    except Exception:
        return []


def _collect_freedb_matches(reader: CDDAReader) -> list[list[Any]]:
    """Return list of metadata matches from FreeDB (each match is list of MetaData)."""
    if freedb is None:
        return []
    try:
        disc_id = freedb.DiscID.from_cddareader(reader)
        matches = list(freedb.perform_lookup(disc_id, FREEDB_SERVER, FREEDB_PORT))
        return matches
    except Exception:
        return []


def _format_match_summary(meta_list: list[Any], index: int) -> str:
    """Format one match for display (e.g. '1. Artist – Album (Year)')."""
    if not meta_list:
        return f"{index}. (no metadata)"
    first = meta_list[0]
    artist = getattr(first, "artist_name", None) or getattr(first, "performer_name", None) or "Unknown"
    album = getattr(first, "album_name", None) or "Unknown"
    year = getattr(first, "year", None) or ""
    if year:
        return f"{index}. {artist} – {album} ({year})"
    return f"{index}. {artist} – {album}"


def _prompt_choice(matches: list[list[Any]]) -> list[Any] | None:
    """Prompt user to select a match; return selected list or None for skip."""
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    try:
        import typer
        typer.echo("Multiple metadata matches:")
        for i, meta_list in enumerate(matches, 1):
            typer.echo(f"  {_format_match_summary(meta_list, i)}")
        prompt = f"Select match [1-{len(matches)}] (or 0 to skip metadata): "
        line = input(prompt).strip()
        choice = int(line)
        if choice == 0:
            return None
        if 1 <= choice <= len(matches):
            return matches[choice - 1]
    except (ValueError, EOFError):
        pass
    return None


def resolve_metadata(
    reader: CDDAReader,
    track_lengths: list[int],
    lookup: bool = True,
    interactive: bool = True,
) -> list[Any] | None:
    """Resolve metadata for all tracks: lookup and optionally prompt for choice.

    Args:
        reader: Open CDDAReader (will not be closed).
        track_lengths: Number of tracks (used only to build empty metadata if needed).
        lookup: If True, perform MusicBrainz and FreeDB lookup.
        interactive: If True and multiple matches, prompt user; else use first match.

    Returns:
        List of MetaData (one per track) or None if no metadata (use empty per-track).
    """
    if audiotools is None:
        return None
    if not lookup:
        return None
    matches: list[list[Any]] = []
    matches.extend(_collect_musicbrainz_matches(reader))
    matches.extend(_collect_freedb_matches(reader))
    # Deduplicate by string representation of first track (same album)
    seen: set[str] = set()
    unique: list[list[Any]] = []
    for meta_list in matches:
        key = _format_match_summary(meta_list, 0)
        if key not in seen:
            seen.add(key)
            unique.append(meta_list)
    if not unique:
        return None
    if interactive:
        chosen = _prompt_choice(unique)
    else:
        chosen = unique[0] if unique else None
    if chosen is None:
        return None
    # Ensure we have one MetaData per track; pad or trim to match track_count
    track_count = len(track_lengths)
    result: list[Any] = []
    for i in range(track_count):
        if i < len(chosen):
            result.append(chosen[i])
        else:
            result.append(audiotools.MetaData(track_number=i + 1, track_total=track_count))
    return result

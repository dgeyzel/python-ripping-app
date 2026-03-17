"""Metadata lookup via MusicBrainz with interactive match selection."""

from __future__ import annotations

from typing import Any

from src.metadata_types import MetaData

try:
    import discid
    import musicbrainzngs
except Exception:
    discid = None  # type: ignore[misc, assignment]
    musicbrainzngs = None  # type: ignore[misc, assignment]


def _get_disc_id(
    device_path: str,
    cue_toc: tuple[int, int, list[int]] | None,
    cue_leadout: int | None,
) -> Any:
    """Return discid.Disc from device or from CUE TOC (first, last, offsets, leadout)."""
    if discid is None:
        return None
    if cue_toc is not None and cue_leadout is not None:
        first, last, offsets = cue_toc
        if first < 1 or last < first or len(offsets) != last - first + 1:
            return None
        try:
            return discid.put(first, last, cue_leadout, offsets)
        except Exception:
            return None
    try:
        return discid.read(device_path)
    except Exception:
        return None


def _musicbrainz_lookup(disc: Any) -> list[list[MetaData]]:
    """Query MusicBrainz by disc id; return list of matches (each match = list of MetaData)."""
    if musicbrainzngs is None or disc is None:
        return []
    musicbrainzngs.set_useragent("cd-ripper", "0.1.0", "https://github.com/cd-ripper")
    try:
        result = musicbrainzngs.get_releases_by_discid(
            disc.id, includes=["artists", "recordings"]
        )
    except Exception:
        return []
    if not result.get("disc") or "release-list" not in result["disc"]:
        return []
    matches: list[list[MetaData]] = []
    for release in result["disc"]["release-list"]:
        artist_name = release.get("artist-credit-phrase") or "Unknown"
        if artist_name == "Unknown":
            artist_credit = release.get("artist-credit", [])
            if artist_credit and isinstance(artist_credit[0], dict):
                artist_name = (
                    artist_credit[0].get("artist", {}).get("name", "Unknown")
                    or "Unknown"
                )
        album_name = release.get("title", "Unknown")
        date = release.get("date", "") or ""
        year = date[:4] if len(date) >= 4 else ""
        medium_list = release.get("medium-list", [])
        if not medium_list:
            matches.append(
                [
                    MetaData(
                        track_number=1,
                        track_total=1,
                        artist_name=artist_name,
                        album_name=album_name,
                        year=year,
                    )
                ]
            )
            continue
        medium = medium_list[0]
        track_list = medium.get("track-list", [])
        meta_list: list[MetaData] = []
        total = len(track_list)
        for i, t in enumerate(track_list):
            rec = t.get("recording", {})
            title = rec.get("title", "")
            meta_list.append(
                MetaData(
                    track_number=i + 1,
                    track_total=total,
                    track_name=title,
                    artist_name=artist_name,
                    album_name=album_name,
                    year=year,
                )
            )
        if meta_list:
            matches.append(meta_list)
    return matches


def _format_match_summary(meta_list: list[MetaData], index: int) -> str:
    """Format one match for display (e.g. '1. Artist – Album (Year)')."""
    if not meta_list:
        return f"{index}. (no metadata)"
    first = meta_list[0]
    artist = first.artist_name or first.performer_name or "Unknown"
    album = first.album_name or "Unknown"
    year = first.year or ""
    if year:
        return f"{index}. {artist} – {album} ({year})"
    return f"{index}. {artist} – {album}"


def _prompt_choice(matches: list[list[MetaData]]) -> list[MetaData] | None:
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
    device_path: str,
    track_lengths: list[int],
    cue_toc: tuple[int, int, list[int]] | None = None,
    cue_leadout: int | None = None,
    lookup: bool = True,
    interactive: bool = True,
) -> list[MetaData] | None:
    """Resolve metadata for all tracks via MusicBrainz.

    Args:
        device_path: CD device path or path to .cue file (for disc ID).
        track_lengths: Number of tracks (for padding).
        cue_toc: If reading from CUE, (first_track, last_track, [start_sector, ...]).
        cue_leadout: If reading from CUE, lead-out sector for discid.put().
        lookup: If True, perform MusicBrainz lookup.
        interactive: If True and multiple matches, prompt user; else use first match.

    Returns:
        List of MetaData (one per track) or None if no metadata.
    """
    if not lookup:
        return None
    disc = _get_disc_id(device_path, cue_toc, cue_leadout)
    matches = _musicbrainz_lookup(disc) if disc else []
    seen: set[str] = set()
    unique: list[list[MetaData]] = []
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
    track_count = len(track_lengths)
    result: list[MetaData] = []
    for i in range(track_count):
        if i < len(chosen):
            meta = chosen[i]
            result.append(
                MetaData(
                    track_number=i + 1,
                    track_total=track_count,
                    track_name=meta.track_name,
                    artist_name=meta.artist_name,
                    album_name=meta.album_name,
                    year=meta.year,
                )
            )
        else:
            result.append(
                MetaData(track_number=i + 1, track_total=track_count)
            )
    return result

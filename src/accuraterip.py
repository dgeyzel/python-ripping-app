"""AccurateRip verification for ripped tracks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from audiotools.cdio import CDDAReader

try:
    import audiotools
    from audiotools import accuraterip as ar_module
except ImportError:
    audiotools = None  # type: ignore[misc, assignment]
    ar_module = None  # type: ignore[misc, assignment]


@dataclass
class VerifyResult:
    """Result of AccurateRip verification for one track."""

    verified: bool
    confidence: int | None
    offset: int


def fetch_ar_matches(reader: CDDAReader) -> dict[int, list[tuple[int, int, int]]]:
    """Fetch AccurateRip expected checksums for the disc.

    Returns:
        Dict mapping track_number (1-based) to list of (confidence, crc, crc2).
        Empty dict if lookup fails or no data.
    """
    if ar_module is None:
        return {}
    try:
        disc_id = ar_module.DiscID.from_cddareader(reader)
        return ar_module.perform_lookup(disc_id)
    except Exception:
        return {}


def verify_track(
    track_number: int,
    total_tracks: int,
    track_pcm_frames: int,
    frame_lists: Iterator[Any],
    ar_matches: dict[int, list[tuple[int, int, int]]],
    initial_offset: int = 0,
) -> VerifyResult:
    """Verify one track's PCM data against AccurateRip.

    Args:
        track_number: 1-based track index.
        total_tracks: Total number of tracks on disc.
        track_pcm_frames: Length of this track in PCM frames.
        frame_lists: Iterator of FrameList objects (from reading the track PCM).
        ar_matches: Result of fetch_ar_matches(reader).
        initial_offset: Sample offset for match_offset (e.g. 0).

    Returns:
        VerifyResult with verified, confidence, and offset.
    """
    if ar_module is None:
        return VerifyResult(verified=False, confidence=None, offset=0)
    matches = ar_matches.get(track_number, [])
    if not matches:
        return VerifyResult(verified=False, confidence=None, offset=0)
    is_first = track_number == 1
    is_last = track_number == total_tracks
    checksum_calc = ar_module.ChecksumV1(
        track_pcm_frames,
        sample_rate=44100,
        is_first=is_first,
        is_last=is_last,
    )
    for fl in frame_lists:
        if fl is not None and len(fl) > 0:
            checksum_calc.update(fl)
    try:
        checksums = checksum_calc.checksums()
    except ValueError:
        return VerifyResult(verified=False, confidence=None, offset=0)
    checksum, confidence, offset = ar_module.match_offset(
        {track_number: matches}, checksums, initial_offset
    )
    verified = confidence is not None and confidence > 0
    return VerifyResult(
        verified=verified,
        confidence=confidence if confidence is not None else 0,
        offset=offset,
    )

"""CD/CUE opening and per-track PCM access using audiotools.cdio."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from audiotools.cdio import CDDAReader

try:
    import audiotools
    from audiotools import cdio
    from audiotools import pcm
except ImportError:
    audiotools = None  # type: ignore[misc, assignment]
    cdio = None  # type: ignore[misc, assignment]
    pcm = None  # type: ignore[misc, assignment]


def get_default_device() -> str:
    """Return default CD device path for the current platform."""
    if audiotools is not None and getattr(audiotools, "DEFAULT_CDROM", None):
        return audiotools.DEFAULT_CDROM
    if sys.platform == "win32":
        return "D:"
    return "/dev/cdrom"


@contextmanager
def open_cd(device: str = ""):
    """Open CD or CUE image and yield (CDDAReader, ordered list of track lengths).

    Yields:
        (reader, track_lengths) where track_lengths is a list of PCM frame counts
        for tracks 1, 2, 3, ... in order. The reader must be used within this
        context; do not use it after the context exits.
    """
    if audiotools is None or cdio is None:
        raise RuntimeError("audiotools is not installed")
    path = device.strip() or get_default_device()
    reader = cdio.CDDAReader(path)
    try:
        # track_lengths is dict: track_number -> pcm frames
        lengths_dict = reader.track_lengths
        if not lengths_dict:
            raise ValueError(f"No tracks found on device: {path}")
        num_tracks = max(lengths_dict)
        track_lengths = [lengths_dict[i] for i in range(1, num_tracks + 1)]
        yield reader, track_lengths
    finally:
        reader.close()


def iter_track_pcm(
    reader: CDDAReader,
    track_lengths: list[int],
) -> Iterator[tuple[int, "pcm.PCMReader"]]:
    """Yield (track_index_1based, pcm_reader) for each track.

    Consumes the CDDAReader; do not use the reader after iteration.
    """
    if audiotools is None or pcm is None:
        raise RuntimeError("audiotools is not installed")
    split_readers = audiotools.pcm_split(reader, track_lengths)
    for idx, pcm_reader in enumerate(split_readers, 1):
        yield idx, pcm_reader

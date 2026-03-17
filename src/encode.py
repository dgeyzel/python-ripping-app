"""Encode CD tracks to one or more formats with metadata and AccurateRip verification."""

from __future__ import annotations

from typing import Any

try:
    import audiotools
except ImportError:
    audiotools = None  # type: ignore[misc, assignment]


def _read_pcm_into_frames(pcm_reader: Any) -> list[Any]:
    """Consume pcm_reader and return list of FrameList objects."""
    frames: list[Any] = []
    try:
        while True:
            fl = pcm_reader.read(4096 * 1024)
            if fl is None or len(fl) == 0:
                break
            frames.append(fl)
    finally:
        try:
            pcm_reader.close()
        except Exception:
            pass
    return frames


class _ReplayablePCMReader:
    """PCMReader that yields from a list of FrameLists (replayable for multiple encodes)."""

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        channel_mask: int,
        bits_per_sample: int,
        frame_lists: list[Any],
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.channel_mask = channel_mask
        self.bits_per_sample = bits_per_sample
        self._frames = frame_lists
        self._index = 0
        self._closed = False

    def read(self, pcm_frames: int) -> Any:
        if self._closed:
            raise ValueError("reader is closed")
        if self._index >= len(self._frames):
            return self._frames[0].__class__(b"") if self._frames else None
        fl = self._frames[self._index]
        self._index += 1
        return fl

    def close(self) -> None:
        self._closed = True


def _get_audio_type(format_name: str) -> Any:
    """Return AudioFile class for format (e.g. 'flac' -> FlacAudio)."""
    if audiotools is None:
        raise RuntimeError("audiotools not installed")
    type_map = getattr(audiotools, "TYPE_MAP", None) or {}
    fmt = format_name.lower()
    if fmt in type_map:
        return type_map[fmt]
    for name, cls in type_map.items():
        if getattr(cls, "SUFFIX", "") == fmt or getattr(cls, "NAME", "") == fmt:
            return cls
    raise ValueError(f"Unknown or unavailable format: {format_name}")


def _get_compression(
    format_name: str,
    quality_map: dict[str, str],
    bitrate_map: dict[str, str] | None = None,
) -> str | None:
    """Return compression/quality/bitrate string for format.

    Bitrate (if provided for this format) takes precedence over quality.
    """
    fmt = format_name.lower()
    if bitrate_map and fmt in bitrate_map:
        return bitrate_map[fmt]
    if quality_map and fmt in quality_map:
        return quality_map[fmt]
    if audiotools is not None:
        defaults = getattr(audiotools, "DEFAULT_QUALITY", None) or {}
        return defaults.get(fmt)
    return None


def run_rip(
    reader: Any,
    track_lengths: list[int],
    metadata_list: list[Any] | None,
    formats: list[str],
    format_to_dir: dict[str, str],
    name_format: str,
    folder_format: str,
    quality_map: dict[str, str],
    bitrate_map: dict[str, str] | None = None,
    verify_accuraterip: bool = True,
) -> None:
    """Rip all tracks to the given formats with metadata and optional AccurateRip verification."""
    if audiotools is None:
        raise RuntimeError("audiotools not installed")
    from src.templates import build_track_dir_and_filename
    from src.accuraterip import fetch_ar_matches, verify_track
    import typer

    num_tracks = len(track_lengths)
    meta_list = metadata_list or [
        audiotools.MetaData(track_number=i + 1, track_total=num_tracks)
        for i in range(num_tracks)
    ]
    # Ensure one metadata per track
    while len(meta_list) < num_tracks:
        meta_list.append(
            audiotools.MetaData(
                track_number=len(meta_list) + 1, track_total=num_tracks
            )
        )
    meta_list = meta_list[:num_tracks]

    ar_matches = fetch_ar_matches(reader) if verify_accuraterip else {}

    split_readers = audiotools.pcm_split(reader, track_lengths)
    track_index = 0
    for pcm_reader in split_readers:
        track_index += 1
        frames = _read_pcm_into_frames(pcm_reader)
        total_frames = sum(len(f) for f in frames)
        meta = meta_list[track_index - 1]

        # AccurateRip verification
        if verify_accuraterip and ar_matches:
            result = verify_track(
                track_number=track_index,
                total_tracks=num_tracks,
                track_pcm_frames=track_lengths[track_index - 1],
                frame_lists=iter(frames),
                ar_matches=ar_matches,
            )
            if result.verified and result.confidence is not None:
                typer.echo(
                    f"Track {track_index}: AccurateRip verified (confidence {result.confidence})"
                )
            else:
                typer.echo(f"Track {track_index}: AccurateRip no match")
        elif verify_accuraterip and not ar_matches:
            typer.echo(f"Track {track_index}: AccurateRip lookup unavailable")

        # Build replayable reader (CDDA is 44100, 2 ch, 16 bit)
        replay = _ReplayablePCMReader(
            sample_rate=44100,
            channels=2,
            channel_mask=3,
            bits_per_sample=16,
            frame_lists=frames,
        )

        for fmt in formats:
            audio_cls = _get_audio_type(fmt)
            suffix = getattr(audio_cls, "SUFFIX", fmt)
            base_dir = format_to_dir.get(fmt, ".")
            full_dir, filename = build_track_dir_and_filename(
                base_dir, folder_format, name_format, meta, suffix
            )
            full_dir.mkdir(parents=True, exist_ok=True)
            out_path = full_dir / filename
            compression = _get_compression(fmt, quality_map, bitrate_map)
            try:
                audio_cls.from_pcm(
                    str(out_path),
                    replay,
                    compression=compression,
                    total_pcm_frames=total_frames,
                )
                if meta is not None and getattr(audio_cls, "supports_metadata", lambda: False)():
                    if audio_cls.supports_metadata():
                        af = audiotools.open(str(out_path))
                        try:
                            af.set_metadata(meta)
                        finally:
                            af.close()
                typer.echo(f"  Wrote {out_path}")
            except Exception as e:
                typer.echo(f"  Error encoding {out_path}: {e}", err=True)
            finally:
                replay._index = 0  # Reset for next format

"""Encode CD tracks to one or more formats with metadata and optional AccurateRip."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any, Callable

LogCallback = Callable[[str, bool], None]  # (message, is_stderr)

from src.metadata_types import MetaData

# Optional: AccurateRip when audiotools is installed
try:
    from audiotools import accuraterip as ar_module
except ImportError:
    ar_module = None  # type: ignore[misc, assignment]

BYTES_PER_FRAME = 4  # CDDA 16-bit stereo

# Default quality when not using audiotools
DEFAULT_QUALITY: dict[str, str] = {"flac": "5", "mp3": "192"}


def _read_pcm_into_frames(pcm_reader: Any) -> list[bytes]:
    """Consume pcm_reader and return list of PCM byte chunks."""
    frames: list[bytes] = []
    try:
        while True:
            chunk = pcm_reader.read(4096 * 1024)
            if chunk is None or len(chunk) == 0:
                break
            if not isinstance(chunk, bytes):
                chunk = bytes(chunk)
            frames.append(chunk)
    finally:
        try:
            pcm_reader.close()
        except Exception:
            pass
    return frames


class _ReplayablePCMReader:
    """Replayable PCM stream from a list of byte chunks (for multiple encodes)."""

    def __init__(
        self,
        sample_rate: int,
        channels: int,
        channel_mask: int,
        bits_per_sample: int,
        frame_lists: list[bytes],
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.channel_mask = channel_mask
        self.bits_per_sample = bits_per_sample
        self._frames = frame_lists
        self._index = 0
        self._closed = False

    def read(self, pcm_frames: int) -> bytes | None:
        if self._closed:
            raise ValueError("reader is closed")
        if self._index >= len(self._frames):
            return b"" if self._frames else None
        chunk = self._frames[self._index]
        self._index += 1
        return chunk

    def close(self) -> None:
        self._closed = True


def _get_compression(
    format_name: str,
    quality_map: dict[str, str],
    bitrate_map: dict[str, str] | None = None,
) -> str | None:
    """Return compression/quality/bitrate string for format."""
    fmt = format_name.lower()
    if bitrate_map and fmt in bitrate_map:
        return bitrate_map[fmt]
    if quality_map and fmt in quality_map:
        return quality_map[fmt]
    return DEFAULT_QUALITY.get(fmt)


def _encode_flac(pcm_bytes: bytes, out_path: Path, compression: str = "5") -> None:
    """Encode raw PCM (44.1kHz 16-bit stereo) to FLAC via subprocess."""
    args = [
        "flac",
        "--force-raw-format",
        "--endian=little",
        "--sign=signed",
        "--channels=2",
        "--bps=16",
        "--sample-rate=44100",
        f"--compression-level={compression}",
        "-o",
        str(out_path),
        "-",
    ]
    proc = subprocess.run(
        args,
        input=pcm_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"flac failed: {proc.stderr.decode(errors='replace') if proc.stderr else 'unknown'}"
        )


def _encode_mp3(pcm_bytes: bytes, out_path: Path, bitrate: str = "192") -> None:
    """Encode raw PCM (44.1kHz 16-bit stereo) to MP3 via lame."""
    args = [
        "lame",
        "-r",
        "-s",
        "44.1",
        "-m",
        "s",
        "-b",
        bitrate,
        "-",
        str(out_path),
    ]
    proc = subprocess.run(
        args,
        input=pcm_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"lame failed: {proc.stderr.decode(errors='replace') if proc.stderr else 'unknown'}"
        )


def _encode_wav(pcm_bytes: bytes, out_path: Path) -> None:
    """Encode raw PCM (44.1kHz 16-bit stereo) to WAV using stdlib wave."""
    with wave.open(str(out_path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(pcm_bytes)


def _apply_metadata(out_path: Path, meta: Any, suffix: str) -> None:
    """Write tags to file using mutagen (FLAC/MP3)."""
    try:
        from mutagen.flac import FLAC
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC
    except ImportError:
        return
    if out_path.suffix.lower() == ".flac":
        try:
            f = FLAC(str(out_path))
            if meta and getattr(meta, "track_name", None):
                f["title"] = [str(meta.track_name)]
            if meta and getattr(meta, "artist_name", None):
                f["artist"] = [str(meta.artist_name)]
            if meta and getattr(meta, "album_name", None):
                f["album"] = [str(meta.album_name)]
            if meta and getattr(meta, "year", None):
                f["date"] = [str(meta.year)]
            if meta and getattr(meta, "track_number", None):
                f["tracknumber"] = [str(meta.track_number)]
            if meta and getattr(meta, "track_total", None):
                f["tracktotal"] = [str(meta.track_total)]
            f.save()
        except Exception:
            pass
    elif out_path.suffix.lower() == ".mp3":
        try:
            try:
                id3 = ID3(str(out_path))
            except Exception:
                id3 = ID3()
            if meta and getattr(meta, "artist_name", None):
                id3.add(TPE1(encoding=3, text=[str(meta.artist_name)]))
            if meta and getattr(meta, "track_name", None):
                id3.add(TIT2(encoding=3, text=[str(meta.track_name)]))
            if meta and getattr(meta, "album_name", None):
                id3.add(TALB(encoding=3, text=[str(meta.album_name)]))
            if meta and getattr(meta, "year", None):
                id3.add(TDRC(encoding=3, text=[str(meta.year)]))
            id3.save(str(out_path))
        except Exception:
            pass


_SUPPORTED_FORMATS = {"flac", "mp3", "wav"}


def _encode_track(
    pcm_bytes: bytes,
    fmt: str,
    out_path: Path,
    compression: str | None,
    meta: Any,
) -> None:
    """Encode one track to the given format and apply metadata."""
    fmt_lower = fmt.lower()
    if fmt_lower not in _SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {fmt}. Supported: {', '.join(sorted(_SUPPORTED_FORMATS))}"
        )
    if fmt_lower == "flac":
        _encode_flac(pcm_bytes, out_path, compression or "5")
    elif fmt_lower == "mp3":
        _encode_mp3(pcm_bytes, out_path, compression or "192")
    elif fmt_lower == "wav":
        _encode_wav(pcm_bytes, out_path)
    if fmt_lower != "wav":
        _apply_metadata(out_path, meta, fmt)


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
    log_callback: LogCallback | None = None,
) -> None:
    """Rip all tracks to the given formats with metadata. AccurateRip if available."""
    import typer

    from src.templates import build_track_dir_and_filename

    def log(msg: str, err: bool = False) -> None:
        if log_callback:
            log_callback(msg, err)
        else:
            typer.echo(msg, err=err)

    num_tracks = len(track_lengths)
    meta_list = metadata_list or [
        MetaData(track_number=i + 1, track_total=num_tracks) for i in range(num_tracks)
    ]
    while len(meta_list) < num_tracks:
        meta_list.append(
            MetaData(track_number=len(meta_list) + 1, track_total=num_tracks)
        )
    meta_list = meta_list[:num_tracks]

    if verify_accuraterip:
        log("AccurateRip: unavailable (install python-audio-tools for verification)")

    split_readers = reader.get_track_readers(track_lengths)
    for track_index, pcm_reader in enumerate(split_readers, 1):
        frames = _read_pcm_into_frames(pcm_reader)
        pcm_bytes = b"".join(frames)
        meta = meta_list[track_index - 1]

        for fmt in formats:
            suffix = fmt.lower()
            base_dir = format_to_dir.get(fmt, ".")
            full_dir, filename = build_track_dir_and_filename(
                base_dir, folder_format, name_format, meta, suffix
            )
            full_dir = Path(full_dir)
            full_dir.mkdir(parents=True, exist_ok=True)
            out_path = full_dir / filename
            compression = _get_compression(fmt, quality_map, bitrate_map)
            try:
                _encode_track(pcm_bytes, fmt, out_path, compression, meta)
                log(f"  Wrote {out_path}")
            except Exception as e:
                log(f"  Error encoding {out_path}: {e}", err=True)

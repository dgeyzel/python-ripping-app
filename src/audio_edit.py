"""Batch audio editing helpers built on top of pydub."""

from __future__ import annotations

import inspect
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import detect_leading_silence

from src.templates import sanitize_path_part

LogCallback = Callable[[str, bool], None]

AVAILABLE_EXPORT_FORMATS: tuple[str, ...] = ("flac", "mp3", "ogg", "wav")
SUPPORTED_INPUT_EXTENSIONS: tuple[str, ...] = (
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
    ".webm",
)
EXPORT_BITRATE_FORMATS = {"aac", "mp3", "ogg", "opus"}
_AUDIO_TOOL_NAMES = {"ffmpeg", "ffprobe", "avconv"}
_WAV_SUFFIX = ".wav"

EDIT_OPERATION_REGISTRY: dict[str, str] = {
    "append_path": "Append a companion file to each source file.",
    "overlay_path": "Overlay a companion file on top of each source file.",
    "sample_width": "Convert sample width.",
    "frame_rate": "Convert sample rate.",
    "channels": "Convert channel count.",
    "normalize_audio": "Normalize peak volume.",
    "gain_db": "Apply a gain adjustment.",
    "pan": "Pan stereo balance.",
    "remove_dc_offset": "Remove DC offset.",
    "trim": "Trim milliseconds from the start and end.",
    "trim_silence": "Trim leading and trailing silence.",
    "reverse": "Reverse playback.",
    "fade": "Apply fade in and fade out.",
}


@dataclass(slots=True)
class AudioEditSettings:
    """Settings used to batch edit audio files."""

    output_dir: Path | None = None
    output_format: str = "mp3"
    filename_suffix: str = "_edited"
    bitrate: str | None = None
    append_path: Path | None = None
    append_crossfade_ms: int = 0
    overlay_path: Path | None = None
    overlay_position_ms: int = 0
    overlay_gain_during_overlay_db: float = 0.0
    overlay_loop: bool = False
    overlay_times: int = 1
    sample_width: int | None = None
    frame_rate: int | None = None
    channels: int | None = None
    normalize_audio: bool = False
    gain_db: float | None = None
    pan: float | None = None
    remove_dc_offset: bool = False
    trim_start_ms: int = 0
    trim_end_ms: int = 0
    trim_silence: bool = False
    silence_thresh: float = -50.0
    silence_chunk_size: int = 10
    reverse: bool = False
    fade_in_ms: int = 0
    fade_out_ms: int = 0


def available_export_formats() -> tuple[str, ...]:
    """Return the export formats exposed in the GUI."""

    return AVAILABLE_EXPORT_FORMATS


def _tool_base_candidates() -> list[Path]:
    """Return possible base directories for bundled executables."""

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", sys.executable))
        if not base.is_dir():
            base = base.parent
        candidates.append(base)

    project_base = Path(__file__).resolve().parents[1]
    if project_base not in candidates:
        candidates.append(project_base)
    return candidates


def _prepend_audio_tool_dirs_to_path() -> None:
    """Prepend bundled tool directories to PATH when available."""

    path_entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    tool_dirs: list[str] = []
    for base in _tool_base_candidates():
        bin_dir = base / "bin"
        if not bin_dir.is_dir():
            continue
        if not any(
            (bin_dir / tool_name).is_file()
            or (bin_dir / f"{tool_name}.exe").is_file()
            for tool_name in _AUDIO_TOOL_NAMES
        ):
            continue
        bin_dir_str = str(bin_dir)
        if bin_dir_str not in path_entries and bin_dir_str not in tool_dirs:
            tool_dirs.append(bin_dir_str)
    if tool_dirs:
        os.environ["PATH"] = os.pathsep.join(tool_dirs + path_entries)


def _resolve_audio_tool_path(name: str) -> str | None:
    """Return a bundled tool path first, then fall back to PATH."""

    for base in _tool_base_candidates():
        for candidate in (base / "bin" / name, base / "bin" / f"{name}.exe"):
            if candidate.is_file():
                return str(candidate)
    for candidate_name in (name, f"{name}.exe"):
        found = shutil.which(candidate_name)
        if found:
            return found
    return None


def _configure_audio_backend() -> str | None:
    """Point pydub at bundled ffmpeg tools when available."""

    _prepend_audio_tool_dirs_to_path()
    converter = _resolve_audio_tool_path("ffmpeg")
    if converter is not None:
        AudioSegment.converter = converter
        setattr(AudioSegment, "ffmpeg", converter)
    ffprobe = _resolve_audio_tool_path("ffprobe")
    if ffprobe is not None:
        AudioSegment.ffprobe = ffprobe
    return converter


def ffmpeg_available() -> bool:
    """Return True when ffmpeg is available via the bundle or PATH."""

    return _configure_audio_backend() is not None


def edit_requires_ffmpeg(
    input_paths: Sequence[str | Path],
    settings: AudioEditSettings,
) -> bool:
    """Return True when this edit batch needs ffmpeg."""

    export_format = settings.output_format.lower().lstrip(".")
    if export_format != "wav":
        return True
    for path in input_paths:
        if Path(path).suffix.lower() != _WAV_SUFFIX:
            return True
    for companion_path in (settings.append_path, settings.overlay_path):
        if (
            companion_path is not None
            and Path(companion_path).suffix.lower() != _WAV_SUFFIX
        ):
            return True
    return False


def describe_ffmpeg_requirement(
    input_paths: Sequence[str | Path],
    settings: AudioEditSettings,
) -> str:
    """Describe why ffmpeg is needed for this edit batch."""

    export_format = settings.output_format.lower().lstrip(".")
    reasons: list[str] = []
    if export_format != "wav":
        reasons.append(f"exporting to {export_format.upper()}")
    if any(Path(path).suffix.lower() != _WAV_SUFFIX for path in input_paths):
        reasons.append("reading non-WAV input files")
    for companion_path in (settings.append_path, settings.overlay_path):
        if (
            companion_path is not None
            and Path(companion_path).suffix.lower() != _WAV_SUFFIX
        ):
            reasons.append("using non-WAV companion files")
            break
    if reasons:
        joined = " and ".join(reasons)
        return f"This edit needs ffmpeg for {joined}."
    return "This edit needs ffmpeg."


def discover_audio_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    """Return audio files from a directory, sorted by path."""

    base = Path(directory)
    if not base.exists():
        raise FileNotFoundError(f"Directory not found: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {base}")

    candidates = base.rglob("*") if recursive else base.iterdir()
    files = [
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
    ]
    return sorted(files, key=lambda path: str(path).lower())


def build_output_path(
    input_path: str | Path,
    output_dir: str | Path | None,
    output_format: str,
    filename_suffix: str = "_edited",
) -> Path:
    """Build the output path for one edited audio file."""

    source_path = Path(input_path)
    target_dir = source_path.parent if output_dir is None else Path(output_dir)
    suffix = output_format.lower().lstrip(".")
    stem = sanitize_path_part(source_path.stem)
    if filename_suffix:
        stem = f"{stem}{filename_suffix}"
    return target_dir / f"{stem}.{suffix}"


def validate_edit_settings(settings: AudioEditSettings) -> None:
    """Validate settings before starting an edit batch."""

    if not str(settings.output_format or "").strip():
        raise ValueError("An output format is required.")
    if settings.append_crossfade_ms < 0:
        raise ValueError("Append crossfade must be zero or positive.")
    if settings.overlay_position_ms < 0:
        raise ValueError("Overlay position must be zero or positive.")
    if settings.overlay_times < 1:
        raise ValueError("Overlay times must be at least 1.")
    if settings.sample_width is not None and settings.sample_width < 1:
        raise ValueError("Sample width must be positive.")
    if settings.frame_rate is not None and settings.frame_rate < 1:
        raise ValueError("Frame rate must be positive.")
    if settings.channels is not None and settings.channels < 1:
        raise ValueError("Channel count must be positive.")
    if settings.pan is not None and not -1.0 <= settings.pan <= 1.0:
        raise ValueError("Pan must be between -1.0 and 1.0.")
    if settings.channels == 1 and settings.pan is not None:
        raise ValueError("Pan requires a stereo output.")
    if settings.trim_start_ms < 0 or settings.trim_end_ms < 0:
        raise ValueError("Trim offsets must be zero or positive.")
    if settings.fade_in_ms < 0 or settings.fade_out_ms < 0:
        raise ValueError("Fade durations must be zero or positive.")
    if settings.silence_chunk_size < 1:
        raise ValueError("Silence chunk size must be positive.")
    if settings.silence_thresh > 0:
        raise ValueError("Silence threshold should be zero or negative dBFS.")

    for attr_name in ("append_path", "overlay_path"):
        companion_path = getattr(settings, attr_name)
        if companion_path is not None and not Path(companion_path).exists():
            raise FileNotFoundError(f"Companion file not found: {companion_path}")


def build_operation_summary(settings: AudioEditSettings) -> list[str]:
    """Return human-readable descriptions of enabled edit operations."""

    summary: list[str] = []
    if settings.append_path:
        append_name = Path(settings.append_path).name
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['append_path']} ({append_name})"
        )
    if settings.overlay_path:
        overlay_name = Path(settings.overlay_path).name
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['overlay_path']} ({overlay_name})"
        )
    if settings.sample_width is not None:
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['sample_width']} -> {settings.sample_width}"
        )
    if settings.frame_rate is not None:
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['frame_rate']} -> {settings.frame_rate}"
        )
    if settings.channels is not None:
        summary.append(f"{EDIT_OPERATION_REGISTRY['channels']} -> {settings.channels}")
    if settings.normalize_audio:
        summary.append(EDIT_OPERATION_REGISTRY["normalize_audio"])
    if settings.gain_db is not None:
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['gain_db']} -> {settings.gain_db:+g} dB"
        )
    if settings.pan is not None:
        summary.append(f"{EDIT_OPERATION_REGISTRY['pan']} -> {settings.pan:+g}")
    if settings.remove_dc_offset:
        summary.append(EDIT_OPERATION_REGISTRY["remove_dc_offset"])
    if settings.trim_start_ms or settings.trim_end_ms:
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['trim']} "
            f"({settings.trim_start_ms} ms / {settings.trim_end_ms} ms)"
        )
    if settings.trim_silence:
        summary.append(EDIT_OPERATION_REGISTRY["trim_silence"])
    if settings.reverse:
        summary.append(EDIT_OPERATION_REGISTRY["reverse"])
    if settings.fade_in_ms or settings.fade_out_ms:
        summary.append(
            f"{EDIT_OPERATION_REGISTRY['fade']} "
            f"({settings.fade_in_ms} ms in / {settings.fade_out_ms} ms out)"
        )
    if not summary:
        summary.append("No edits selected.")
    return summary


def _load_audio(
    path: str | Path,
    cache: dict[Path, AudioSegment] | None = None,
) -> AudioSegment:
    """Load one audio file and optionally reuse a cached copy."""

    resolved = Path(path).expanduser().resolve(strict=False)
    if cache is not None and resolved in cache:
        return cache[resolved]
    try:
        segment = AudioSegment.from_file(resolved)
    except OSError as exc:
        if _is_missing_ffmpeg_error(exc):
            raise _missing_ffmpeg_error("Audio import") from exc
        raise
    if cache is not None:
        cache[resolved] = segment
    return segment


def _trim_trailing_silence(
    segment: AudioSegment,
    silence_thresh: float,
    chunk_size: int,
) -> AudioSegment:
    """Remove silence from the end of a segment."""

    trailing_ms = _detect_leading_silence_compat(
        segment.reverse(),
        silence_thresh=silence_thresh,
        chunk_size=chunk_size,
    )
    if trailing_ms <= 0:
        return segment
    if trailing_ms >= len(segment):
        return segment[:0]
    return segment[: len(segment) - trailing_ms]


def _detect_leading_silence_compat(
    segment: AudioSegment,
    silence_thresh: float,
    chunk_size: int,
) -> int:
    """Call detect_leading_silence with the parameter name this pydub build expects."""

    params = inspect.signature(detect_leading_silence).parameters
    if "silence_threshold" in params:
        return detect_leading_silence(
            segment,
            silence_threshold=silence_thresh,
            chunk_size=chunk_size,
        )
    return detect_leading_silence(
        segment,
        silence_thresh=silence_thresh,
        chunk_size=chunk_size,
    )


def _is_missing_ffmpeg_error(exc: OSError) -> bool:
    """Return True when pydub failed because ffmpeg or a related tool is missing."""

    candidates = [
        getattr(exc, "filename", None),
        getattr(exc, "filename2", None),
        str(exc),
    ]
    if getattr(exc, "winerror", None) == 2 and not ffmpeg_available():
        return True
    for candidate in candidates:
        if not candidate:
            continue
        candidate_text = str(candidate).lower()
        candidate_name = Path(str(candidate)).name.lower().removesuffix(".exe")
        if candidate_name in _AUDIO_TOOL_NAMES:
            return True
        if any(tool in candidate_text for tool in _AUDIO_TOOL_NAMES):
            return True
    return False


def _missing_ffmpeg_error(action: str) -> RuntimeError:
    """Return a user-facing error for missing ffmpeg."""

    return RuntimeError(
        f"{action} failed because ffmpeg or ffprobe was not found. "
        "Install both tools or use a build that includes them, then restart the app."
    )


def apply_edit_settings(
    segment: AudioSegment,
    settings: AudioEditSettings,
    companion_cache: dict[Path, AudioSegment] | None = None,
) -> AudioSegment:
    """Apply the selected edit settings to a single audio segment."""

    validate_edit_settings(settings)
    cache = companion_cache if companion_cache is not None else {}
    result = segment

    if settings.append_path:
        result = result.append(
            _load_audio(settings.append_path, cache),
            crossfade=settings.append_crossfade_ms,
        )
    if settings.overlay_path:
        result = result.overlay(
            _load_audio(settings.overlay_path, cache),
            position=settings.overlay_position_ms,
            gain_during_overlay=settings.overlay_gain_during_overlay_db,
            loop=settings.overlay_loop,
            times=settings.overlay_times,
        )
    if settings.sample_width is not None:
        result = result.set_sample_width(settings.sample_width)
    if settings.frame_rate is not None:
        result = result.set_frame_rate(settings.frame_rate)
    if settings.channels is not None:
        result = result.set_channels(settings.channels)
    if settings.normalize_audio:
        result = normalize(result)
    if settings.gain_db is not None:
        result = result.apply_gain(settings.gain_db)
    if settings.pan is not None:
        result = result.pan(settings.pan)
    if settings.remove_dc_offset:
        if hasattr(result, "remove_dc_offset"):
            result = result.remove_dc_offset()
        else:
            raise NotImplementedError(
                "remove_dc_offset is unavailable in this pydub version."
            )
    if settings.trim_start_ms or settings.trim_end_ms:
        start_ms = min(max(settings.trim_start_ms, 0), len(result))
        end_ms = len(result) - max(settings.trim_end_ms, 0)
        if end_ms < start_ms:
            end_ms = start_ms
        result = result[start_ms:end_ms]
    if settings.trim_silence:
        leading_ms = _detect_leading_silence_compat(
            result,
            silence_thresh=settings.silence_thresh,
            chunk_size=settings.silence_chunk_size,
        )
        if leading_ms:
            result = result[leading_ms:]
        result = _trim_trailing_silence(
            result,
            silence_thresh=settings.silence_thresh,
            chunk_size=settings.silence_chunk_size,
        )
    if settings.reverse:
        result = result.reverse()
    if settings.fade_in_ms:
        result = result.fade_in(duration=settings.fade_in_ms)
    if settings.fade_out_ms:
        result = result.fade_out(duration=settings.fade_out_ms)
    return result


def run_batch_edit(
    input_paths: Sequence[str | Path],
    settings: AudioEditSettings,
    log_callback: LogCallback | None = None,
) -> list[Path]:
    """Edit a batch of audio files and export the results."""

    validate_edit_settings(settings)
    sources = [Path(path).expanduser() for path in input_paths]
    if not sources:
        raise ValueError("Select at least one audio file.")
    if edit_requires_ffmpeg(sources, settings) and not ffmpeg_available():
        raise RuntimeError(
            describe_ffmpeg_requirement(sources, settings)
            + " Install ffmpeg, add it to PATH, and restart the app."
        )

    companion_cache: dict[Path, AudioSegment] = {}
    outputs: list[Path] = []
    first_error: Exception | None = None

    def log(message: str, is_error: bool = False) -> None:
        if log_callback is not None:
            log_callback(message, is_error)

    log(
        "Applying edits: " + ", ".join(build_operation_summary(settings)),
        False,
    )
    export_format = settings.output_format.lower().lstrip(".")

    for source in sources:
        resolved_source = source.resolve(strict=False)
        if not resolved_source.exists():
            log(f"Missing input file: {resolved_source}", True)
            continue

        try:
            segment = _load_audio(resolved_source)
            edited = apply_edit_settings(
                segment,
                settings,
                companion_cache=companion_cache,
            )
            target_dir = settings.output_dir or resolved_source.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            output_path = build_output_path(
                resolved_source,
                target_dir,
                export_format,
                settings.filename_suffix,
            )
            export_kwargs: dict[str, Any] = {"format": export_format}
            if settings.bitrate and export_format in EXPORT_BITRATE_FORMATS:
                export_kwargs["bitrate"] = settings.bitrate
            try:
                exported = edited.export(str(output_path), **export_kwargs)
            except OSError as exc:
                if _is_missing_ffmpeg_error(exc):
                    raise _missing_ffmpeg_error("Audio export") from exc
                raise
            try:
                exported.close()
            except Exception:
                pass
            outputs.append(output_path)
            log(f"Wrote {output_path}", False)
        except Exception as exc:
            if first_error is None:
                first_error = exc
            log(f"Edit error for {resolved_source}: {exc}", True)

    if not outputs:
        if first_error is not None:
            raise first_error
        raise RuntimeError("No audio files were edited successfully.")
    return outputs

"""Tests for batch audio editing helpers."""

from pathlib import Path

import pytest
from pydub import AudioSegment
from pydub.generators import Sine


def _make_tone(duration_ms: int = 1000):
    """Create a small test tone for pydub-based tests."""

    return Sine(440).to_audio_segment(duration=duration_ms)


def test_available_export_formats_contains_common_formats():
    """The helper exposes the formats used by the edit tab."""

    from src.audio_edit import available_export_formats

    assert "mp3" in available_export_formats()
    assert "wav" in available_export_formats()


def test_build_output_path_uses_suffix():
    """Output paths keep the source stem and add the configured suffix."""

    from src.audio_edit import build_output_path

    output = build_output_path(
        Path("music track.wav"),
        Path("out"),
        "mp3",
        "_edited",
    )
    assert output.name == "music track_edited.mp3"
    assert output.parent == Path("out")


def test_edit_requires_ffmpeg_detects_common_cases():
    """The helper flags non-WAV edits and skips WAV-to-WAV batches."""

    from src.audio_edit import AudioEditSettings, edit_requires_ffmpeg

    wav_only_settings = AudioEditSettings(output_format="wav")
    assert edit_requires_ffmpeg([Path("track.wav")], wav_only_settings) is False
    assert edit_requires_ffmpeg([Path("track.mp3")], wav_only_settings) is True

    mp3_settings = AudioEditSettings(output_format="mp3")
    assert edit_requires_ffmpeg([Path("track.wav")], mp3_settings) is True


def test_ffmpeg_available_prefers_bundled_binary(tmp_path, monkeypatch):
    """Bundled ffmpeg should win over a PATH installation."""

    import src.audio_edit as audio_edit

    bundle_bin = tmp_path / "bin"
    bundle_bin.mkdir()
    bundled_ffmpeg = bundle_bin / "ffmpeg.exe"
    bundled_ffprobe = bundle_bin / "ffprobe.exe"
    bundled_ffmpeg.touch()
    bundled_ffprobe.touch()

    def fake_which(name: str) -> str | None:
        if name in {"ffmpeg", "ffmpeg.exe"}:
            return r"C:\system\ffmpeg.exe"
        if name in {"ffprobe", "ffprobe.exe"}:
            return r"C:\system\ffprobe.exe"
        return None

    monkeypatch.setattr(audio_edit.sys, "frozen", True, raising=False)
    monkeypatch.setattr(audio_edit.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(audio_edit.shutil, "which", fake_which)
    monkeypatch.setattr(audio_edit.AudioSegment, "converter", "ffmpeg", raising=False)
    monkeypatch.setattr(audio_edit.AudioSegment, "ffprobe", "ffprobe", raising=False)

    assert audio_edit.ffmpeg_available() is True
    assert audio_edit.AudioSegment.converter == str(bundled_ffmpeg)
    assert audio_edit.AudioSegment.ffprobe == str(bundled_ffprobe)


def test_ffmpeg_available_uses_project_bin_when_not_frozen(
    tmp_path, monkeypatch
):
    """Source runs should also use a local bin/ directory."""

    import src.audio_edit as audio_edit

    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    bundle_bin = project_root / "bin"
    src_dir.mkdir(parents=True)
    bundle_bin.mkdir()
    bundled_ffmpeg = bundle_bin / "ffmpeg.exe"
    bundled_ffprobe = bundle_bin / "ffprobe.exe"
    bundled_ffmpeg.touch()
    bundled_ffprobe.touch()

    fake_module_file = src_dir / "audio_edit.py"
    fake_module_file.touch()

    def fake_which(name: str) -> str | None:
        return None

    monkeypatch.setattr(audio_edit.sys, "frozen", False, raising=False)
    monkeypatch.setattr(audio_edit, "__file__", str(fake_module_file))
    monkeypatch.setattr(audio_edit.shutil, "which", fake_which)
    monkeypatch.setattr(audio_edit.AudioSegment, "converter", "ffmpeg", raising=False)
    monkeypatch.setattr(audio_edit.AudioSegment, "ffprobe", "ffprobe", raising=False)

    assert audio_edit.ffmpeg_available() is True
    assert audio_edit.AudioSegment.converter == str(bundled_ffmpeg)
    assert audio_edit.AudioSegment.ffprobe == str(bundled_ffprobe)


def test_ffmpeg_available_prepends_project_bin_to_path(tmp_path, monkeypatch):
    """The bundled bin/ directory should be added to PATH for pydub."""

    import src.audio_edit as audio_edit

    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    bundle_bin = project_root / "bin"
    src_dir.mkdir(parents=True)
    bundle_bin.mkdir()
    (bundle_bin / "ffmpeg.exe").touch()
    (bundle_bin / "ffprobe.exe").touch()
    fake_module_file = src_dir / "audio_edit.py"
    fake_module_file.touch()

    monkeypatch.setattr(audio_edit.sys, "frozen", False, raising=False)
    monkeypatch.setattr(audio_edit, "__file__", str(fake_module_file))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(audio_edit.AudioSegment, "converter", "ffmpeg", raising=False)
    monkeypatch.setattr(audio_edit.AudioSegment, "ffprobe", "ffprobe", raising=False)

    assert audio_edit.ffmpeg_available() is True
    assert audio_edit.shutil.which("ffprobe").lower() == str(
        bundle_bin / "ffprobe.exe"
    ).lower()


def test_ffmpeg_available_falls_back_to_path(tmp_path, monkeypatch):
    """PATH resolution still works when no bundled ffmpeg is present."""

    import src.audio_edit as audio_edit

    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    fake_module_file = src_dir / "audio_edit.py"
    fake_module_file.touch()

    def fake_which(name: str) -> str | None:
        if name in {"ffmpeg", "ffmpeg.exe"}:
            return r"C:\system\ffmpeg.exe"
        if name in {"ffprobe", "ffprobe.exe"}:
            return r"C:\system\ffprobe.exe"
        return None

    monkeypatch.setattr(audio_edit.sys, "frozen", True, raising=False)
    monkeypatch.setattr(audio_edit.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(audio_edit, "__file__", str(fake_module_file))
    monkeypatch.setattr(audio_edit.shutil, "which", fake_which)
    monkeypatch.setattr(audio_edit.AudioSegment, "converter", "ffmpeg", raising=False)
    monkeypatch.setattr(audio_edit.AudioSegment, "ffprobe", "ffprobe", raising=False)

    assert audio_edit.ffmpeg_available() is True
    assert audio_edit.AudioSegment.converter == r"C:\system\ffmpeg.exe"
    assert audio_edit.AudioSegment.ffprobe == r"C:\system\ffprobe.exe"


def test_discover_audio_files_finds_supported_files(tmp_path):
    """discover_audio_files returns supported files recursively."""

    from src.audio_edit import discover_audio_files

    (tmp_path / "a.wav").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("ignore me")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.mp3").write_bytes(b"")

    files = discover_audio_files(tmp_path)

    assert [path.name for path in files] == ["a.wav", "b.mp3"]


def test_validate_edit_settings_rejects_pan_for_mono():
    """Mono output cannot use panning."""

    from src.audio_edit import AudioEditSettings, validate_edit_settings

    settings = AudioEditSettings(
        output_dir=None,
        channels=1,
        pan=0.25,
    )

    with pytest.raises(ValueError, match="Pan requires a stereo output"):
        validate_edit_settings(settings)


def test_apply_edit_settings_changes_basic_audio_properties():
    """Common edit operations update the resulting segment."""

    from src.audio_edit import AudioEditSettings, apply_edit_settings

    segment = _make_tone(1000)
    settings = AudioEditSettings(
        output_dir=None,
        sample_width=2,
        frame_rate=22050,
        channels=1,
        normalize_audio=True,
        gain_db=3.0,
        trim_start_ms=100,
        trim_end_ms=150,
        reverse=True,
        fade_in_ms=50,
        fade_out_ms=50,
    )

    result = apply_edit_settings(segment, settings)

    assert result.channels == 1
    assert result.frame_rate == 22050
    assert result.sample_width == 2
    assert len(result) == 750


def test_apply_edit_settings_trims_leading_silence():
    """Silence trimming works with the installed pydub signature."""

    from pydub import AudioSegment
    from src.audio_edit import AudioEditSettings, apply_edit_settings

    segment = AudioSegment.silent(150) + _make_tone(350)
    settings = AudioEditSettings(
        output_dir=None,
        trim_silence=True,
        silence_thresh=-40.0,
        silence_chunk_size=10,
    )

    result = apply_edit_settings(segment, settings)

    assert len(result) < len(segment)
    assert len(result) >= 300


def test_run_batch_edit_writes_wav_output(tmp_path):
    """Batch editing should export the transformed file."""

    from src.audio_edit import AudioEditSettings, run_batch_edit

    input_path = tmp_path / "input.wav"
    output_dir = tmp_path / "edited"
    _make_tone(1000).export(input_path, format="wav").close()

    settings = AudioEditSettings(
        output_dir=output_dir,
        output_format="wav",
        filename_suffix="_edited",
        trim_start_ms=100,
        fade_out_ms=50,
    )

    outputs = run_batch_edit([input_path], settings)

    assert len(outputs) == 1
    output_path = outputs[0]
    assert output_path.exists()
    assert output_path.name == "input_edited.wav"
    assert output_path.parent == output_dir
    edited = AudioSegment.from_file(output_path)
    assert len(edited) == 900


def test_run_batch_edit_reports_missing_ffmpeg_before_export(tmp_path, monkeypatch):
    """Missing ffmpeg gets a clear user-facing message before export starts."""

    import src.audio_edit as audio_edit

    input_path = tmp_path / "input.wav"
    _make_tone(500).export(input_path, format="wav").close()

    monkeypatch.setattr(audio_edit, "ffmpeg_available", lambda: False)

    settings = audio_edit.AudioEditSettings(
        output_dir=tmp_path / "edited",
        output_format="mp3",
    )

    with pytest.raises(
        RuntimeError, match="This edit needs ffmpeg for exporting to MP3"
    ):
        audio_edit.run_batch_edit([input_path], settings)

"""Tests for encode module (run_rip and helpers)."""

import pytest


def test_get_audio_type_raises_without_audiotools(monkeypatch):
    """_get_audio_type raises when audiotools is None."""
    from src.encode import _get_audio_type
    import src.encode as enc
    monkeypatch.setattr(enc, "audiotools", None)
    with pytest.raises(RuntimeError, match="audiotools"):
        _get_audio_type("flac")


def test_replayable_reader_has_expected_attrs():
    """_ReplayablePCMReader has sample_rate, channels, bits_per_sample."""
    from src.encode import _ReplayablePCMReader
    r = _ReplayablePCMReader(44100, 2, 3, 16, [])
    assert r.sample_rate == 44100
    assert r.channels == 2
    assert r.bits_per_sample == 16


def test_read_pcm_into_frames_returns_list():
    """_read_pcm_into_frames returns a list (empty for exhausted reader)."""
    from src.encode import _read_pcm_into_frames
    class EmptyReader:
        def read(self, n):
            return None

        def close(self):
            pass
    frames = _read_pcm_into_frames(EmptyReader())
    assert isinstance(frames, list)
    assert len(frames) == 0


def test_get_compression_prefers_bitrate_over_quality():
    """_get_compression uses bitrate_map when present, else quality_map."""
    from src.encode import _get_compression
    quality_map = {"mp3": "2", "flac": "8"}
    bitrate_map = {"mp3": "320"}
    assert _get_compression("mp3", quality_map, bitrate_map) == "320"
    assert _get_compression("flac", quality_map, bitrate_map) == "8"
    assert _get_compression("flac", quality_map, None) == "8"

"""Tests for bitrate support and validation."""

import pytest

from src.bitrates import (
    get_supported_bitrates,
    is_bitrate_supported,
    format_supported_list,
)


def test_get_supported_bitrates_mp3():
    """MP3 returns list of common bitrates."""
    out = get_supported_bitrates("mp3")
    assert out is not None
    assert "320" in out
    assert "256" in out
    assert "128" in out


def test_get_supported_bitrates_flac():
    """FLAC returns compression levels 0-8."""
    out = get_supported_bitrates("flac")
    assert out is not None
    assert out == [str(i) for i in range(9)]


def test_get_supported_bitrates_case_insensitive():
    """Format name is case-insensitive."""
    assert get_supported_bitrates("MP3") == get_supported_bitrates("mp3")


def test_get_supported_bitrates_unknown_returns_none():
    """Unknown format returns None."""
    assert get_supported_bitrates("wav") is None
    assert get_supported_bitrates("unknown") is None


def test_is_bitrate_supported_mp3_valid():
    """Valid MP3 bitrates are accepted."""
    assert is_bitrate_supported("mp3", "320") is True
    assert is_bitrate_supported("mp3", "128") is True
    assert is_bitrate_supported("mp3", " 320 ") is True


def test_is_bitrate_supported_mp3_invalid():
    """Invalid MP3 bitrate is rejected."""
    assert is_bitrate_supported("mp3", "999") is False
    assert is_bitrate_supported("mp3", "100") is False


def test_is_bitrate_supported_unknown_format_allowed():
    """Unknown format allows any value (encoder may reject later)."""
    assert is_bitrate_supported("wav", "anything") is True


def test_format_supported_list_mp3():
    """Supported list for MP3 is comma-separated."""
    out = format_supported_list("mp3")
    assert "320" in out
    assert "128" in out
    assert ", " in out or len(out) > 3


def test_format_supported_list_unknown_format():
    """Unknown format returns placeholder message."""
    out = format_supported_list("wav")
    assert "no list defined" in out or "format" in out.lower()

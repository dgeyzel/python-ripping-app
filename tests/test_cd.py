"""Tests for CD/CUE and Windows drive detection."""

import sys

import pytest

from src.cd import _is_windows_drive, _windows_drive_device, get_default_device


def test_get_default_device_platform():
    """get_default_device returns D: on Windows, /dev/cdrom otherwise."""
    if sys.platform == "win32":
        assert get_default_device() == "D:"
    else:
        assert get_default_device() == "/dev/cdrom"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive detection")
def test_is_windows_drive_true_on_windows():
    """_is_windows_drive returns True for D:, E:, E\\ on Windows."""
    assert _is_windows_drive("D:") is True
    assert _is_windows_drive("E:") is True
    assert _is_windows_drive("E:\\") is True
    assert _is_windows_drive("D") is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive detection")
def test_is_windows_drive_false_for_non_drive():
    """_is_windows_drive returns False for /dev/cdrom and .cue on Windows."""
    assert _is_windows_drive("/dev/cdrom") is False
    assert _is_windows_drive("file.cue") is False
    assert _is_windows_drive("") is False


def test_is_windows_drive_false_on_non_windows(monkeypatch):
    """_is_windows_drive returns False when platform is not win32."""
    monkeypatch.setattr(sys, "platform", "linux")
    assert _is_windows_drive("D:") is False
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _is_windows_drive("D:") is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive device path")
def test_windows_drive_device_normalizes():
    """_windows_drive_device returns \\\\.\\X: form."""
    assert _windows_drive_device("D:") == "\\\\.\\D:"
    assert _windows_drive_device("e") == "\\\\.\\E:"

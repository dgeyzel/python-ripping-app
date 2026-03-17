"""CD/CUE opening and per-track PCM access using pycdio, CUE+BIN, or Windows IOCTL."""

from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import cdio
    import pycdio
except ImportError:
    cdio = None  # type: ignore[misc, assignment]
    pycdio = None  # type: ignore[misc, assignment]

# CDDA: 44100 Hz, 16-bit stereo -> 4 bytes per frame, 588 frames per sector
BYTES_PER_FRAME = 4
FRAMES_PER_SECTOR = 588
BYTES_PER_SECTOR = 2352

# --- Windows CD-ROM (Win32 IOCTL) ---
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_READONLY = 0x01
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    # ntddcdrm.h: FILE_DEVICE_CD_ROM=2, METHOD_BUFFERED=0, FILE_READ_ACCESS=1
    # CTL_CODE(DeviceType, Function, Method, Access)
    def _ctl_code(dev: int, func: int, method: int = 0, access: int = 1) -> int:
        return (dev << 16) | (access << 14) | (func << 2) | method

    _FILE_DEVICE_CD_ROM = 0x00000002
    IOCTL_CDROM_READ_TOC = _ctl_code(_FILE_DEVICE_CD_ROM, 0x0000)
    IOCTL_CDROM_RAW_READ = _ctl_code(_FILE_DEVICE_CD_ROM, 0x0006)
    # Track mode: YellowBook = 2 is CDDA for audio
    TRACK_MODE_CDDA = 2
    RAW_SECTOR_SIZE = 2352
    # DiskOffset for RAW_READ: sector index * 2048 (per MSDN)
    WINDOWS_RAW_READ_OFFSET_MULTIPLIER = 2048
else:
    _kernel32 = None


def get_default_device() -> str:
    """Return default CD device path for the current platform."""
    if sys.platform == "win32":
        return "D:"
    return "/dev/cdrom"


def _is_windows_drive(path: str) -> bool:
    """Return True if path looks like a Windows drive letter (e.g. D:, E:\\)."""
    if sys.platform != "win32":
        return False
    s = path.strip().rstrip("\\")
    if not s:
        return False
    if len(s) == 1:
        return s.isalpha()
    if len(s) == 2 and s[1] == ":":
        return s[0].isalpha()
    return False


def _windows_drive_device(path: str) -> str:
    """Return \\\\.\\X: form for CreateFileW from a drive path like D: or E."""
    s = path.strip().rstrip("\\")
    letter = s[0].upper() if s else "D"
    return f"\\\\.\\{letter}:"


def _parse_cue(cue_path: str) -> tuple[str, list[tuple[int, int]]]:
    """Parse CUE file; return (bin_file_path, [(start_sector, end_sector), ...]).

    Paths in CUE are relative to the CUE file directory.
    """
    path = Path(cue_path).resolve()
    if not path.is_file():
        raise ValueError(f"CUE file not found: {cue_path}")
    base_dir = path.parent
    bin_path = ""
    tracks: list[tuple[int, int]] = []
    current_track_start: int | None = None
    prev_index: int | None = None

    def msf_to_sector(m: int, s: int, f: int) -> int:
        return m * 60 * 75 + s * 75 + f

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("REM"):
                continue
            if line.upper().startswith("FILE "):
                match = re.match(r'FILE\s+"([^"]+)"\s+\w+', line, re.I)
                if match:
                    bin_path = str(base_dir / match.group(1))
                continue
            if line.upper().startswith("TRACK "):
                if current_track_start is not None and prev_index is not None:
                    tracks.append((current_track_start, prev_index))
                num = line.split()[1]
                if num.isdigit():
                    current_track_start = None
                continue
            if line.upper().startswith("INDEX 01 "):
                parts = re.split(r"[\s:]+", line, 3)[-1].strip().split()
                if len(parts) >= 3:
                    m, s, f = int(parts[0]), int(parts[1]), int(parts[2])
                    sector = msf_to_sector(m, s, f)
                    if current_track_start is None:
                        current_track_start = sector
                    prev_index = sector

    if current_track_start is not None and prev_index is not None:
        tracks.append((current_track_start, prev_index))

    if not bin_path or not tracks:
        raise ValueError(f"Invalid CUE or no tracks: {cue_path}")
    return bin_path, tracks


class _CueTrackReader:
    """Reads one track's PCM from a BIN file."""

    def __init__(
        self,
        bin_path: str,
        start_sector: int,
        end_sector: int,
    ) -> None:
        self._bin_path = bin_path
        self._start = start_sector * BYTES_PER_SECTOR
        self._length = (end_sector - start_sector + 1) * BYTES_PER_SECTOR
        self._pos = 0
        self._closed = False

    def read(self, size: int) -> bytes:
        if self._closed or self._pos >= self._length:
            return b""
        with open(self._bin_path, "rb") as f:
            f.seek(self._start + self._pos)
            to_read = min(size, self._length - self._pos)
            data = f.read(to_read)
            self._pos += len(data)
            return data

    def close(self) -> None:
        self._closed = True


class _CueReader:
    """Reader for CUE+BIN image; provides get_track_readers."""

    def __init__(self, cue_path: str) -> None:
        self._bin_path, sector_ranges = _parse_cue(cue_path)
        self._sector_ranges = sector_ranges
        self._track_lengths = [
            (end - start + 1) * FRAMES_PER_SECTOR for start, end in sector_ranges
        ]

    @property
    def track_lengths(self) -> list[int]:
        return self._track_lengths

    @property
    def cue_toc(self) -> tuple[int, int, list[int]]:
        """Return (first_track, last_track, [start_sector, ...]) for discid.put()."""
        n = len(self._sector_ranges)
        offsets = [start for start, _ in self._sector_ranges]
        return (1, n, offsets)

    @property
    def cue_leadout(self) -> int:
        """Lead-out sector (first sector after last track) for discid.put()."""
        return self._sector_ranges[-1][1] + 1

    def get_track_readers(
        self, track_lengths: list[int]
    ) -> list[Any]:
        """Return one reader per track (same length list as track_lengths)."""
        readers = []
        for i, (start, end) in enumerate(self._sector_ranges):
            readers.append(_CueTrackReader(self._bin_path, start, end))
        return readers

    def close(self) -> None:
        pass


class _DeviceTrackReader:
    """Reads one track's PCM from a pycdio device."""

    def __init__(
        self,
        device: Any,
        lsn_start: int,
        lsn_end: int,
    ) -> None:
        self._device = device
        self._lsn_start = lsn_start
        self._lsn_end = lsn_end
        self._current_lsn = lsn_start
        self._closed = False

    def read(self, size: int) -> bytes:
        if self._closed or self._current_lsn > self._lsn_end:
            return b""
        # Read in sector chunks (2352 bytes each)
        sectors_to_read = min(
            (size + BYTES_PER_SECTOR - 1) // BYTES_PER_SECTOR,
            self._lsn_end - self._current_lsn + 1,
        )
        if sectors_to_read <= 0:
            return b""
        try:
            blocks, data = self._device.read_sectors(
                self._current_lsn,
                pycdio.READ_MODE_AUDIO,
                sectors_to_read,
            )
        except Exception:
            return b""
        self._current_lsn += blocks
        raw = data if isinstance(data, bytes) else data.encode("latin-1")
        if len(raw) > sectors_to_read * BYTES_PER_SECTOR:
            raw = raw[: sectors_to_read * BYTES_PER_SECTOR]
        return raw

    def close(self) -> None:
        self._closed = True


class _DeviceReader:
    """Reader for physical CD via pycdio; provides get_track_readers."""

    def __init__(self, device: Any, track_lsn_ranges: list[tuple[int, int]]) -> None:
        self._device = device
        self._track_lsn_ranges = track_lsn_ranges
        self._track_lengths = [
            (end - start + 1) * FRAMES_PER_SECTOR for start, end in track_lsn_ranges
        ]

    @property
    def track_lengths(self) -> list[int]:
        return self._track_lengths

    @property
    def cue_toc(self) -> None:
        """No CUE TOC for device reader."""
        return None

    def get_track_readers(
        self, track_lengths: list[int]
    ) -> list[Any]:
        readers = []
        for start, end in self._track_lsn_ranges:
            readers.append(_DeviceTrackReader(self._device, start, end))
        return readers

    def close(self) -> None:
        try:
            self._device.close()
        except Exception:
            pass


# --- Windows CD-ROM reader classes (only used when sys.platform == "win32") ---
if sys.platform == "win32":
    import struct as _struct

    class _WindowsTrackReader:
        """Reads one track's PCM from a Windows CD via IOCTL_CDROM_RAW_READ."""

        def __init__(
            self,
            handle: int,
            start_sector: int,
            end_sector: int,
        ) -> None:
            self._handle = handle
            self._start_sector = start_sector
            self._end_sector = end_sector
            self._current_sector = start_sector
            self._closed = False

        def read(self, size: int) -> bytes:
            if self._closed or self._current_sector > self._end_sector:
                return b""
            sectors_to_read = min(
                (size + BYTES_PER_SECTOR - 1) // BYTES_PER_SECTOR,
                self._end_sector - self._current_sector + 1,
            )
            if sectors_to_read <= 0:
                return b""
            buf = ctypes.create_string_buffer(sectors_to_read * RAW_SECTOR_SIZE)
            offset = self._current_sector * WINDOWS_RAW_READ_OFFSET_MULTIPLIER
            raw_read_info = ctypes.create_string_buffer(16)
            _struct.pack_into(
                "<QII", raw_read_info, 0, offset, sectors_to_read, TRACK_MODE_CDDA
            )
            bytes_returned = wintypes.DWORD(0)
            ok = _kernel32.DeviceIoControl(
                self._handle,
                IOCTL_CDROM_RAW_READ,
                raw_read_info,
                16,
                buf,
                ctypes.sizeof(buf),
                ctypes.byref(bytes_returned),
                None,
            )
            if not ok:
                return b""
            n_read = sectors_to_read * RAW_SECTOR_SIZE
            self._current_sector += sectors_to_read
            return buf.raw[:n_read]

        def close(self) -> None:
            self._closed = True

    class _WindowsReader:
        """Reader for physical CD via Windows IOCTL; same interface as _DeviceReader."""

        def __init__(self, handle: int, track_lsn_ranges: list[tuple[int, int]]) -> None:
            self._handle = handle
            self._track_lsn_ranges = track_lsn_ranges
            self._track_lengths = [
                (end - start + 1) * FRAMES_PER_SECTOR
                for start, end in track_lsn_ranges
            ]

        @property
        def track_lengths(self) -> list[int]:
            return self._track_lengths

        @property
        def cue_toc(self) -> None:
            return None

        def get_track_readers(self, track_lengths: list[int]) -> list[Any]:
            readers = []
            for start, end in self._track_lsn_ranges:
                readers.append(_WindowsTrackReader(self._handle, start, end))
            return readers

        def close(self) -> None:
            if self._handle != INVALID_HANDLE_VALUE and self._handle is not None:
                _kernel32.CloseHandle(self._handle)
                self._handle = INVALID_HANDLE_VALUE

    def _open_windows_cd(path: str) -> _WindowsReader:
        """Open Windows CD drive and return _WindowsReader with track ranges."""
        device_path = _windows_drive_device(path)
        handle = _kernel32.CreateFileW(
            device_path,
            GENERIC_READ,
            0x00000001,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_READONLY,
            None,
        )
        if handle is None or handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            raise OSError(
                err,
                f"Cannot open CD drive {path}. "
                "Try running as administrator or ensure a disc is in the drive.",
            )
        toc_size = 2 + 2 + 100 * 8
        toc_buf = ctypes.create_string_buffer(toc_size)
        bytes_returned = wintypes.DWORD(0)
        ok = _kernel32.DeviceIoControl(
            handle,
            IOCTL_CDROM_READ_TOC,
            None,
            0,
            toc_buf,
            toc_size,
            ctypes.byref(bytes_returned),
            None,
        )
        if not ok:
            _kernel32.CloseHandle(handle)
            raise OSError(
                ctypes.get_last_error(),
                f"Failed to read TOC from {path}. Is there an audio CD in the drive?",
            )
        raw = toc_buf.raw[: bytes_returned.value]
        first_track = raw[2]
        last_track = raw[3]
        if first_track > last_track or last_track == 0:
            _kernel32.CloseHandle(handle)
            raise ValueError(f"No tracks found on device: {path}")
        track_ranges = []
        for i in range(first_track, last_track + 1):
            idx = i - first_track
            entry_off = 4 + idx * 8
            if entry_off + 8 > len(raw):
                break
            control = raw[entry_off + 1] & 0x0F
            if (control & 0x04) != 0:
                continue
            addr_bytes = raw[entry_off + 4 : entry_off + 8]
            fr, sec, min_ = addr_bytes[0], addr_bytes[1], addr_bytes[2]
            start_lba = (min_ * 60 + sec) * 75 + fr
            next_off = 4 + (idx + 1) * 8
            if next_off + 8 <= len(raw):
                nb = raw[next_off + 4 : next_off + 8]
                end_lba = (nb[2] * 60 + nb[1]) * 75 + nb[0] - 1
            else:
                end_lba = start_lba + 1
            track_ranges.append((start_lba, end_lba))
        if not track_ranges:
            _kernel32.CloseHandle(handle)
            raise ValueError(f"No audio tracks on device: {path}")
        return _WindowsReader(handle, track_ranges)


@contextmanager
def open_cd(device: str = ""):
    """Open CD or CUE image and yield (reader, track_lengths).

    Yields:
        (reader, track_lengths) where track_lengths is a list of PCM frame counts
        for tracks 1, 2, 3, ... Reader has get_track_readers(track_lengths).
    """
    path = (device or get_default_device()).strip()
    if path.lower().endswith(".cue"):
        reader = _CueReader(path)
        try:
            yield reader, reader.track_lengths
        finally:
            reader.close()
        return

    if sys.platform == "win32" and _is_windows_drive(path):
        try:
            reader = _open_windows_cd(path)
            try:
                yield reader, reader.track_lengths
            finally:
                reader.close()
        except Exception as e:
            raise ValueError(f"Cannot open CD device {path}: {e}") from e
        return

    if cdio is None or pycdio is None:
        raise RuntimeError(
            "pycdio is required for CD device access. Install: pip install pycdio"
        )
    driver_id = pycdio.DRIVER_LINUX if sys.platform != "win32" else pycdio.DRIVER_DEVICE
    dev = cdio.Device(driver_id)
    try:
        dev.open(path)
    except Exception as e:
        raise ValueError(f"Cannot open CD device {path}: {e}") from e

    try:
        num_tracks = dev.get_num_tracks()
        if num_tracks <= 0:
            raise ValueError(f"No tracks found on device: {path}")
        track_lsn_ranges: list[tuple[int, int]] = []
        for i in range(1, num_tracks + 1):
            try:
                t = dev.get_track(i)
                if t.get_format() != pycdio.TRACK_FORMAT_AUDIO:
                    continue
                start = t.get_lsn()
                end = t.get_last_lsn()
                track_lsn_ranges.append((start, end))
            except Exception:
                break
        if not track_lsn_ranges:
            raise ValueError(f"No audio tracks on device: {path}")
        reader = _DeviceReader(dev, track_lsn_ranges)
        try:
            yield reader, reader.track_lengths
        finally:
            reader.close()
    except Exception:
        try:
            dev.close()
        except Exception:
            pass
        raise


def iter_track_pcm(
    reader: Any,
    track_lengths: list[int],
) -> Iterator[tuple[int, Any]]:
    """Yield (track_index_1based, pcm_reader) for each track."""
    for idx, pcm_reader in enumerate(reader.get_track_readers(track_lengths), 1):
        yield idx, pcm_reader

"""Supported encoding bitrates (or quality/compression values) per format.

Used to validate user-specified bitrate and to show supported values when invalid.
"""

# Per-format supported values. Values are strings as used by the encoder.
# For lossy formats these are typically bitrates in kbps; for FLAC, compression 0-8.
SUPPORTED_BITRATES: dict[str, list[str]] = {
    "flac": [str(i) for i in range(9)],  # compression 0-8
    "mp3": [
        "32", "40", "48", "56", "64", "80", "96", "112",
        "128", "160", "192", "224", "256", "320",
    ],
    "ogg": [str(i) for i in range(-1, 11)],  # Vorbis quality -1 to 10
    "vorbis": [str(i) for i in range(-1, 11)],
    "opus": ["64", "96", "128", "160", "192", "256"],
    "aac": ["96", "128", "160", "192", "256", "320"],
    "m4a": ["96", "128", "160", "192", "256", "320"],
}


def get_supported_bitrates(format_name: str) -> list[str] | None:
    """Return list of supported bitrate/quality values for a format, or None if unknown.

    Args:
        format_name: Format key (e.g. 'flac', 'mp3').

    Returns:
        List of supported values as strings, or None if format has no defined set.
    """
    fmt = format_name.lower().strip()
    return SUPPORTED_BITRATES.get(fmt)


def is_bitrate_supported(format_name: str, value: str) -> bool:
    """Return True if the given value is supported for the format.

    Args:
        format_name: Format key (e.g. 'flac', 'mp3').
        value: User-supplied bitrate/quality string.

    Returns:
        True if supported, False otherwise.
    """
    supported = get_supported_bitrates(format_name)
    if supported is None:
        return True  # unknown format: allow and let encoder reject if needed
    return value.strip() in supported


def format_supported_list(format_name: str) -> str:
    """Return a human-readable list of supported bitrates for the format.

    Args:
        format_name: Format key (e.g. 'flac', 'mp3').

    Returns:
        String suitable for display (e.g. "128, 160, 192, 224, 256, 320").
    """
    supported = get_supported_bitrates(format_name)
    if supported is None:
        return "(no list defined for this format)"
    return ", ".join(supported)

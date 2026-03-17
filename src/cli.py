"""Typer CLI app and commands for CD ripping."""

try:
    import audiotools
except ImportError:
    audiotools = None  # type: ignore[misc, assignment]

import typer

app = typer.Typer(
    name="cdrip",
    help="Rip audio from CD to one or more formats with metadata and AccurateRip verification.",
)


def _require_audiotools() -> None:
    """Raise if audiotools is not installed."""
    if audiotools is None:
        typer.echo(
            "Error: audiotools is required. Install from source:\n"
            "  git clone https://github.com/tuffy/python-audio-tools.git\n"
            "  cd python-audio-tools && pip install .",
            err=True,
        )
        raise typer.Exit(1)


@app.command()
def rip(
    format: list[str] = typer.Option(
        ["flac"],
        "--format",
        "-f",
        help="Output format(s), e.g. flac, mp3. Can be repeated.",
    ),
    output_dir: list[str] = typer.Option(
        [],
        "--output-dir",
        "-o",
        help="Per-format output dir as format:path, e.g. flac:./flac. Can be repeated.",
    ),
    name_format: str = typer.Option(
        "%(track_number)2.2d - %(track_name)s",
        "--name-format",
        help="Filename template (audiotools %% placeholders).",
    ),
    folder_format: str = typer.Option(
        "",
        "--folder-format",
        help="Folder structure template under output dir (%% placeholders).",
    ),
    device: str = typer.Option(
        "",
        "--device",
        "-d",
        help="CD device path or path to .cue file. Default: platform-specific.",
    ),
    no_lookup: bool = typer.Option(
        False,
        "--no-lookup",
        help="Skip MusicBrainz/FreeDB metadata lookup.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Use first metadata match without prompting.",
    ),
    verify_accuraterip: bool = typer.Option(
        True,
        "--verify-accuraterip/--no-verify-accuraterip",
        help="Verify each track with AccurateRip.",
    ),
    quality: list[str] = typer.Option(
        [],
        "--quality",
        "-q",
        help="Per-format quality, e.g. flac:8 or mp3:320. Can be repeated.",
    ),
    bitrate: list[str] = typer.Option(
        [],
        "--bitrate",
        "-b",
        help="Per-format encoding bitrate, e.g. mp3:320 or flac:8. Can be repeated.",
    ),
) -> None:
    """Rip CD to one or more formats with metadata and optional AccurateRip verification."""
    _require_audiotools()
    from src.cd import open_cd
    from src.encode import run_rip
    from src.metadata import resolve_metadata
    from src.bitrates import is_bitrate_supported, format_supported_list

    # Resolve output dirs: parse format:path, default current dir for single format
    format_to_dir: dict[str, str] = {}
    for spec in output_dir:
        if ":" in spec:
            f, _, p = spec.partition(":")
            format_to_dir[f.strip().lower()] = p.strip()
    for f in format:
        f_lower = f.lower()
        if f_lower not in format_to_dir:
            format_to_dir[f_lower] = "."

    # Quality map
    quality_map: dict[str, str] = {}
    for spec in quality:
        if ":" in spec:
            f, _, q = spec.partition(":")
            quality_map[f.strip().lower()] = q.strip()

    # Bitrate map with validation
    bitrate_map: dict[str, str] = {}
    for spec in bitrate:
        if ":" in spec:
            f, _, b = spec.partition(":")
            fmt_key = f.strip().lower()
            value = b.strip()
            if not is_bitrate_supported(fmt_key, value):
                supported = format_supported_list(fmt_key)
                typer.echo(
                    f"Unsupported bitrate '{value}' for format '{fmt_key}'.",
                    err=True,
                )
                typer.echo(
                    f"Supported bitrates for {fmt_key}: {supported}",
                    err=True,
                )
                raise typer.Exit(1)
            bitrate_map[fmt_key] = value

    try:
        with open_cd(device) as (reader, track_lengths):
            metadata_list = resolve_metadata(
                reader, track_lengths, lookup=not no_lookup, interactive=not no_interactive
            )
            run_rip(
                reader=reader,
                track_lengths=track_lengths,
                metadata_list=metadata_list,
                formats=[f.lower() for f in format],
                format_to_dir=format_to_dir,
                name_format=name_format,
                folder_format=folder_format or "%(album_name)s",
                quality_map=quality_map,
                bitrate_map=bitrate_map,
                verify_accuraterip=verify_accuraterip,
            )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command("list")
def list_cd(
    device: str = typer.Option(
        "",
        "--device",
        "-d",
        help="CD device path or path to .cue file.",
    ),
) -> None:
    """List CD tracks and show metadata if lookup is available."""
    _require_audiotools()
    from src.cd import open_cd
    from src.metadata import resolve_metadata

    try:
        with open_cd(device) as (reader, track_lengths):
            n = len(track_lengths)
            typer.echo(f"Tracks: {n}")
            for i, length in enumerate(track_lengths, 1):
                typer.echo(f"  Track {i}: {length} PCM frames")
            metadata_list = resolve_metadata(
                reader, track_lengths, lookup=True, interactive=False
            )
            if metadata_list:
                for i, meta in enumerate(metadata_list, 1):
                    artist = getattr(meta, "artist_name", None) or ""
                    title = getattr(meta, "track_name", None) or ""
                    typer.echo(f"  {i}. {artist} - {title}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

"""Typer CLI app and commands for CD ripping."""

import pathlib
import typer

app = typer.Typer(
    name="cdrip",
    help="Rip audio from CD to one or more formats with metadata (AccurateRip optional).",
)

config_app = typer.Typer(help="Export or import settings to/from a TOML file.")
app.add_typer(config_app, name="config")


@config_app.command("export")
def config_export(
    output: pathlib.Path = typer.Option(
        ...,
        "--output",
        "-o",
        path_type=pathlib.Path,
        help="Path to write the TOML config file.",
    ),
) -> None:
    """Export current default configurations to a TOML file."""
    from src.config import DEFAULT_CONFIG, save_config

    save_config(output, DEFAULT_CONFIG)
    typer.echo(f"Exported settings to {output}")


@config_app.command("import")
def config_import(
    path: pathlib.Path = typer.Argument(
        ...,
        path_type=pathlib.Path,
        help="Path to the TOML config file to import.",
    ),
) -> None:
    """Validate and show path to use for rip --config. Does not change CLI state."""
    from src.config import load_config

    try:
        cfg = load_config(path)
        typer.echo(f"Valid config: {path}")
        typer.echo(f"Use: cdrip rip --config {path}")
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Invalid config: {e}", err=True)
        raise typer.Exit(1)


def _apply_config_to_rip_options(
    config_file: pathlib.Path | None,
    format: list[str],
    output_dir: list[str],
    name_format: str,
    folder_format: str,
    device: str,
    no_lookup: bool,
    no_interactive: bool,
    verify_accuraterip: bool,
    quality: list[str],
    bitrate: list[str],
) -> tuple[
    list[str],
    list[str],
    str,
    str,
    str,
    bool,
    bool,
    bool,
    list[str],
    list[str],
]:
    """If config_file is set, use it as base; CLI args override when non-empty."""
    if not config_file or not config_file.exists():
        return (
            format,
            output_dir,
            name_format,
            folder_format,
            device,
            no_lookup,
            no_interactive,
            verify_accuraterip,
            quality,
            bitrate,
        )
    from src.config import load_config

    cfg = load_config(config_file)
    if not format or format == ["flac"]:
        format = cfg["formats"]
    if not output_dir and cfg.get("output_dirs"):
        output_dir = [f"{k}:{v}" for k, v in cfg["output_dirs"].items()]
    if not name_format or name_format == "%(track_number)2.2d - %(track_name)s":
        name_format = cfg.get("name_format") or "%(track_number)2.2d - %(track_name)s"
    if not folder_format:
        folder_format = cfg.get("folder_format") or ""
    if not device:
        device = cfg.get("device") or ""
    if not no_lookup:
        no_lookup = cfg.get("no_lookup", False)
    if not no_interactive:
        no_interactive = cfg.get("no_interactive", False)
    verify_accuraterip = cfg.get("verify_accuraterip", True)
    if not quality and cfg.get("quality"):
        quality = [f"{k}:{v}" for k, v in cfg["quality"].items()]
    if not bitrate and cfg.get("bitrate"):
        bitrate = [f"{k}:{v}" for k, v in cfg["bitrate"].items()]
    return (
        formats,
        output_dir,
        name_format,
        folder_format,
        device,
        no_lookup,
        no_interactive,
        verify_accuraterip,
        quality,
        bitrate,
    )


@app.command()
def rip(
    config: pathlib.Path | None = typer.Option(
        None,
        "--config",
        "-c",
        path_type=pathlib.Path,
        help="Load settings from TOML file. CLI options override file values.",
    ),
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
        help="Filename template (%% placeholders: track_number, track_name, artist_name, album_name, year).",
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
        help="Skip MusicBrainz metadata lookup.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Use first metadata match without prompting.",
    ),
    verify_accuraterip: bool = typer.Option(
        True,
        "--verify-accuraterip/--no-verify-accuraterip",
        help="Show AccurateRip status (verification requires python-audio-tools).",
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
    from src.bitrates import format_supported_list, is_bitrate_supported
    from src.cd import get_default_device, open_cd
    from src.encode import run_rip
    from src.metadata import resolve_metadata

    (
        format,
        output_dir,
        name_format,
        folder_format,
        device,
        no_lookup,
        no_interactive,
        verify_accuraterip,
        quality,
        bitrate,
    ) = _apply_config_to_rip_options(
        config,
        format,
        output_dir,
        name_format,
        folder_format,
        device,
        no_lookup,
        no_interactive,
        verify_accuraterip,
        quality,
        bitrate,
    )

    device_path = (device or get_default_device()).strip()

    format_to_dir: dict[str, str] = {}
    for spec in output_dir:
        if ":" in spec:
            f, _, p = spec.partition(":")
            format_to_dir[f.strip().lower()] = p.strip()
    for f in format:
        f_lower = f.lower()
        if f_lower not in format_to_dir:
            format_to_dir[f_lower] = "."

    quality_map: dict[str, str] = {}
    for spec in quality:
        if ":" in spec:
            f, _, q = spec.partition(":")
            quality_map[f.strip().lower()] = q.strip()

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
        with open_cd(device_path) as (reader, track_lengths):
            cue_toc = getattr(reader, "cue_toc", None)
            cue_leadout = getattr(reader, "cue_leadout", None)
            metadata_list = resolve_metadata(
                device_path,
                track_lengths,
                cue_toc=cue_toc,
                cue_leadout=cue_leadout,
                lookup=not no_lookup,
                interactive=not no_interactive,
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
    from src.cd import get_default_device, open_cd
    from src.metadata import resolve_metadata

    device_path = (device or get_default_device()).strip()
    try:
        with open_cd(device_path) as (reader, track_lengths):
            n = len(track_lengths)
            typer.echo(f"Tracks: {n}")
            for i, length in enumerate(track_lengths, 1):
                typer.echo(f"  Track {i}: {length} PCM frames")
            cue_toc = getattr(reader, "cue_toc", None)
            cue_leadout = getattr(reader, "cue_leadout", None)
            metadata_list = resolve_metadata(
                device_path,
                track_lengths,
                cue_toc=cue_toc,
                cue_leadout=cue_leadout,
                lookup=True,
                interactive=False,
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

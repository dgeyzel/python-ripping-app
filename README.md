# CD Ripper

A cross-platform (Windows and Linux) application to rip audio from a CD to one or more formats (FLAC, MP3, WAV) with MusicBrainz metadata lookup, configurable naming, and optional AccurateRip verification. Use the **CLI** or the **desktop GUI**.

## Requirements

- **Python** 3.10+
- **System (Linux)**: For physical CD reading, install **pycdio** (`pip install pycdio`) and libcdio (e.g. `libcdio-dev`). **flac** and **lame** for encoding.
- **System (Windows)**: Physical CD access uses the Windows API (no pycdio required). **flac** and **lame** must be on PATH. You can also rip from a **CUE sheet** (with BIN image). If opening the CD drive fails, try running as administrator.
- **Edit tab**: Install **ffmpeg** and ensure it is on PATH for source runs.
  A local `bin/` directory next to the project, or a packaged build's `bin/`
  folder, can also provide **ffmpeg/ffprobe** for pydub-based editing and
  export of compressed formats.

## Installation

```bash
uv sync
# or: pip install -e .
```

No separate audiotools install. AccurateRip verification is optional; install python-audio-tools from source if you want verification (see below).

## Desktop GUI

The GUI uses **CustomTkinter** (included in the project dependencies) and Python’s **tkinter** (standard library; on Linux you may need `python3-tk`). Run the graphical interface (Linux and Windows):

```bash
uv run cdrip-gui
```

The GUI provides:

- **List CD**: Choose device or CUE file, list tracks and MusicBrainz metadata.
- **Rip CD**: Set device, output formats (FLAC, MP3, WAV), per-format output dirs, quality/bitrate, and options for metadata lookup and AccurateRip. Rip runs in the background with a log.
- **Edit**: Load one or more music files and apply batch edits with pydub, including gain, normalize, trim, fade, reverse, channel conversion, pan, silence trimming, append, and overlay before exporting the results.
- **Filename and folder format**: Each position in the format is a dropdown; select the token (track number, track name, artist, album, year, extension, separators, etc.) for that slot. Add or remove slots with **+ Add** and **×**. A live preview shows the resulting path/filename pattern.

## CLI Usage

- **Rip a CD** to one or more formats with MusicBrainz metadata lookup:

  ```bash
  uv run cdrip rip -f flac -f mp3 -o flac:./flac -o mp3:./mp3
  ```

- **Per-format output directory**: `--output-dir` / `-o` takes `format:path`, e.g. `flac:./music/flac`, `mp3:./music/mp3`.

- **Filename template**: `--name-format` uses placeholders: `%(track_number)2.2d`, `%(track_name)s`, `%(artist_name)s`, `%(album_name)s`, `%(year)s`, `%(suffix)s`.

- **Folder structure**: `--folder-format` e.g. `"%(year)s/%(artist_name)s/%(album_name)s"` (sanitized for the filesystem).

- **Quality / bitrate**: `--quality` / `-q` or `--bitrate` / `-b` as `format:value`, e.g. `flac:8`, `mp3:320`.

- **Device**: `--device` / `-d`: path to CD device (e.g. `/dev/cdrom`, `D:`) or path to a **.cue** file (with same-directory BIN image).

- **Metadata**: By default MusicBrainz is queried by disc ID. Use `--no-interactive` to take the first match, or `--no-lookup` to skip lookup.

- **AccurateRip**: Shown as unavailable by default. To enable verification, install python-audio-tools from source (see below); then AccurateRip can be used when reading via that backend.

- **List tracks** (no encoding):

  ```bash
  uv run cdrip list -d /dev/cdrom
  ```

## Examples

- Rip to FLAC only:

  ```bash
  uv run cdrip rip -f flac
  ```

- Rip from a CUE file (e.g. after creating an image on Windows):

  ```bash
  uv run cdrip rip -f flac -d path/to/disc.cue -o flac:./out
  ```

- Rip to MP3 at 320 kbps and FLAC at compression level 8:

  ```bash
  uv run cdrip rip -f mp3 -f flac --bitrate mp3:320 --bitrate flac:8
  ```

## Optional: AccurateRip verification

To get AccurateRip verification (when reading from a physical CD with audiotools), install python-audio-tools from source:

```bash
git clone https://github.com/tuffy/python-audio-tools.git
cd python-audio-tools
pip install .
```

The CLI works without it; you will see "AccurateRip: unavailable" when verification is requested.

## Building executables

You can build standalone executables (Windows `.exe` or Linux binaries) with **PyInstaller**:

```bash
uv sync --extra build-exe
pyinstaller cdrip.spec
pyinstaller cdrip_gui.spec
```

Output: `dist/cdrip`, `dist/cdrip-gui` (or `.exe` on Windows). The apps use
**flac**, **lame**, **ffmpeg**, and **ffprobe** from the system PATH unless you
bundle them in the project’s `bin/` folder before building (see [Building
executables](docs/building-executables.md)).

## Development

```bash
uv sync --extra dev
uv run pytest
```

## License

This software is licensed under the GPLv3.
See the license file in this repo for more information.

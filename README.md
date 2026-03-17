# CD Ripper CLI

A cross-platform (Windows and Linux) command-line application to rip audio from a CD to one or more formats (e.g. FLAC, MP3) with metadata lookup, configurable naming, and AccurateRip verification.

## Requirements

- **Python** 3.10+
- **audiotools** (Python Audio Tools) – not on PyPI; install from source (see below).
- **System (Linux)**: libcdio for CD reading; LAME for MP3 encoding; FLAC is built into audiotools.
- **System (Windows)**: Use a CUE sheet / CD image path if libcdio is not available, or install libcdio.

## Installation

### 1. Create environment and install this package

```bash
uv sync
# or: pip install -e .
```

### 2. Install audiotools (required for ripping)

audiotools is not on PyPI. Install from source:

```bash
git clone https://github.com/tuffy/python-audio-tools.git
cd python-audio-tools
pip install .
```

On Linux you may need system libraries first (e.g. `libcdio-dev`, `libmp3lame-dev`). On Windows, CD access may require libcdio or using a CUE/image file instead of a physical drive.

## Usage

- **Rip a CD** to one or more formats with metadata lookup and AccurateRip verification:

  ```bash
  uv run cdrip rip -f flac -f mp3 -o flac:./flac -o mp3:./mp3
  ```

- **Per-format output directory**: `--output-dir` / `-o` takes `format:path`, e.g. `flac:./music/flac`, `mp3:./music/mp3`.

- **Filename template**: `--name-format` uses audiotools placeholders, e.g.  
  `"%(track_number)2.2d - %(artist_name)s - %(track_name)s"`.

- **Folder structure**: `--folder-format` e.g. `"%(year)s/%(artist_name)s/%(album_name)s"` (sanitized for the filesystem).

- **Quality**: `--quality` / `-q` sets per-format quality/compression as `format:value`, e.g. `flac:8`, `mp3:320`. Can be repeated.

- **Bitrate**: `--bitrate` / `-b` sets per-format encoding bitrate as `format:value`, e.g. `mp3:320`, `flac:8`. Can be repeated. If a value is unsupported for that format, the app exits with a list of supported bitrates (e.g. MP3: 32–320 kbps; FLAC: compression 0–8). When both quality and bitrate are set for a format, bitrate is used.

- **Device**: `--device` / `-d`: path to CD device (e.g. `/dev/cdrom`, `D:`) or path to a `.cue` file.

- **Metadata**: By default MusicBrainz and FreeDB are queried. If multiple album matches are found, you are prompted to choose. Use `--no-interactive` to always take the first match, or `--no-lookup` to skip lookup.

- **AccurateRip**: Verification is on by default. For each track you get either "Track N: AccurateRip verified (confidence X)" or "Track N: AccurateRip no match". Use `--no-verify-accuraterip` to skip. CUE/images may have no AccurateRip data; that is skipped without error.

- **Interactive metadata**: When multiple album matches are returned (MusicBrainz/FreeDB), a numbered list is shown and you are prompted to select one (or 0 to skip metadata). With a single match, that match is used without prompting.

- **List tracks** (no encoding):

  ```bash
  uv run cdrip list -d /dev/cdrom
  ```

## Examples

- Rip to FLAC only into current directory:
  ```bash
  uv run cdrip rip -f flac
  ```

- Rip to FLAC and MP3 with separate dirs and custom naming:
  ```bash
  uv run cdrip rip -f flac -f mp3 -o flac:~/music/flac -o mp3:~/music/mp3 --name-format "%(track_number)2.2d - %(track_name)s"
  ```

- Rip from a CUE file (e.g. after creating an image on Windows):
  ```bash
  uv run cdrip rip -f flac -d path/to/disc.cue -o flac:./out
  ```

- Non-interactive (first metadata match, no prompt):
  ```bash
  uv run cdrip rip -f flac --no-interactive
  ```

- Rip to MP3 at 320 kbps and FLAC at compression level 8:
  ```bash
  uv run cdrip rip -f mp3 -f flac --bitrate mp3:320 --bitrate flac:8
  ```

## Development

```bash
uv sync --extra dev
uv run pytest
```

## License

See repository license. This project uses Python Audio Tools (audiotools), which is GPL-2.0.

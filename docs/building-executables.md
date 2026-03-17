# Building Windows and Linux executables

The CLI (`cdrip`) and GUI (`cdrip-gui`) can be packaged as standalone executables with **PyInstaller**. Build on Windows to get `.exe` files; build on Linux to get native binaries.

## Prerequisites

- Python 3.10+
- Project dependencies and PyInstaller:

  ```bash
  uv sync --extra build-exe
  # or: pip install -e ".[build-exe]"
  ```

## Build commands

Run from the **project root**:

```bash
# CLI executable (cdrip or cdrip.exe)
pyinstaller cdrip.spec

# GUI executable (cdrip-gui or cdrip-gui.exe)
pyinstaller cdrip_gui.spec
```

Output goes to `dist/`:

- **Windows**: `dist/cdrip.exe`, `dist/cdrip-gui.exe`
- **Linux**: `dist/cdrip`, `dist/cdrip-gui`

To build both in one go:

```bash
pyinstaller cdrip.spec && pyinstaller cdrip_gui.spec
```

Or use the helper script (from project root):

```bash
uv run python scripts/build_exe.py
```

## flac and lame

Encoding to FLAC and MP3 requires **flac** and **lame**:

- **Without bundling**: Install them on the system and ensure they are on PATH. The built executable will call them via PATH.
- **With bundling**: Before running PyInstaller, put the correct binaries in the project’s `bin/` directory:
  - **Windows**: `flac.exe` and `lame.exe`
  - **Linux**: `flac` and `lame` (from distro packages or static builds)

See `bin/README.md` for details. If `bin/` is missing or empty, the app falls back to PATH.

## Optional features not in the bundle

- **AccurateRip**: Requires python-audio-tools (install from source). Not bundled; that feature will show as unavailable in the built exe unless the user installs it.
- **Linux CD access**: Physical CD reading on Linux may require pycdio and libcdio; not bundled.

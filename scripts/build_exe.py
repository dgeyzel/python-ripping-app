"""Build both CLI and GUI executables with PyInstaller. Run from project root."""

import sys

def main() -> None:
    try:
        import PyInstaller.__main__ as pyi
    except ImportError:
        print("PyInstaller not installed. Run: uv sync --extra build-exe", file=sys.stderr)
        sys.exit(1)

    for spec in ("cdrip.spec", "cdrip_gui.spec"):
        rc = pyi.run([spec])
        if rc is not None and rc != 0:
            sys.exit(rc)
    print("Built: dist/cdrip, dist/cdrip-gui (or .exe on Windows)")

if __name__ == "__main__":
    main()

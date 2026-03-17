"""Pytest fixtures and configuration."""

import sys
from pathlib import Path

# Ensure src is on path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

"""Resolves bundled asset paths, both when run from source and from a frozen
PyInstaller exe."""
from __future__ import annotations

import os
import sys


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

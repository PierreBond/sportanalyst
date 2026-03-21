from __future__ import annotations

import sys
from pathlib import Path

libs_path = str(Path(__file__).parent / "libs")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

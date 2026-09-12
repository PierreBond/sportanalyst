from __future__ import annotations

import sys
from pathlib import Path

project_root = str(Path(__file__).parent)
libs_path = str(Path(__file__).parent / "libs")
for p in [project_root, libs_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

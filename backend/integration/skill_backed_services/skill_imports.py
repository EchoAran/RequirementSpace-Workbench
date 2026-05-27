from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any


_INTEGRATION_DIR = Path(__file__).resolve().parents[1]


def import_skill_module(skill_dir: str, module_name: str) -> Any:
    skill_path = _INTEGRATION_DIR / skill_dir
    skill_path_text = str(skill_path)
    if skill_path_text not in sys.path:
        sys.path.insert(0, skill_path_text)
    return import_module(module_name)


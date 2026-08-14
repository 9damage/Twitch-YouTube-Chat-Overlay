from __future__ import annotations

import html
import re
from pathlib import Path


def safe_text(value: str) -> str:
    return html.escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value))


def resource_path(relative: str) -> Path:
    import sys
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


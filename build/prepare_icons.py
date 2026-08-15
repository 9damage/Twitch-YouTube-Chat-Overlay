from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


def resize_icon(source: Path, destination: Path, size: int) -> None:
    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"Cannot load icon source: {source}")
    scaled = image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not scaled.save(str(destination), "PNG"):
        raise RuntimeError(f"Cannot save prepared icon: {destination}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: prepare_icons.py APP_SOURCE TRAY_SOURCE APP_DESTINATION TRAY_DESTINATION"
        )
    resize_icon(Path(sys.argv[1]), Path(sys.argv[3]), 512)
    resize_icon(Path(sys.argv[2]), Path(sys.argv[4]), 64)

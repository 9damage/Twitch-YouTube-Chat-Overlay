from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage


def generate_ico(source: Path, destination: Path) -> None:
    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"Cannot load icon source: {source}")

    sizes = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
    payloads: list[bytes] = []
    for size in sizes:
        scaled = image.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not scaled.save(buffer, "PNG"):
            raise RuntimeError(f"Cannot encode {size}x{size} icon")
        payloads.append(bytes(data))

    header_size = 6 + 16 * len(payloads)
    offset = header_size
    entries = bytearray()
    for size, payload in zip(sizes, payloads, strict=True):
        dimension = 0 if size == 256 else size
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        offset += len(payload)

    destination.write_bytes(struct.pack("<HHH", 0, 1, len(payloads)) + entries + b"".join(payloads))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: generate_ico.py SOURCE.png DESTINATION.ico")
    generate_ico(Path(sys.argv[1]), Path(sys.argv[2]))

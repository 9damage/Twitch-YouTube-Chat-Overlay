from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class _DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


class SecretStore:
    """Stores credentials encrypted for the current Windows user with DPAPI."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        if os.name != "nt" or not self.path.exists():
            return {}
        encrypted = self.path.read_bytes()
        input_blob, input_buffer = _blob(encrypted)
        output_blob = _DataBlob()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
        ):
            raise ctypes.WinError()
        try:
            plain = ctypes.string_at(output_blob.data, output_blob.size)
            data = json.loads(plain.decode("utf-8"))
            return {str(key): str(value) for key, value in data.items()}
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.data)
            del input_buffer

    def save(self, values: dict[str, str]) -> None:
        if os.name != "nt":
            return
        plain = json.dumps(values, ensure_ascii=False).encode("utf-8")
        input_blob, input_buffer = _blob(plain)
        output_blob = _DataBlob()
        description = "Twitch + YouTube Chat Overlay credentials"
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(input_blob), description, None, None, None, 0, ctypes.byref(output_blob)
        ):
            raise ctypes.WinError()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(ctypes.string_at(output_blob.data, output_blob.size))
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.data)
            del input_buffer


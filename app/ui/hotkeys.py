from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
from collections.abc import Callable

from PySide6.QtCore import QAbstractNativeEventFilter

from app.utils.windows import parse_hotkey


class GlobalHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, window_handle: int, bindings: dict[int, tuple[str, Callable[[], None]]]) -> None:
        super().__init__()
        self.window_handle = window_handle
        self.bindings = bindings
        self.registered: list[int] = []
        if os.name == "nt":
            for hotkey_id, (sequence, _) in bindings.items():
                modifiers, key = parse_hotkey(sequence)
                if key and ctypes.windll.user32.RegisterHotKey(window_handle, hotkey_id, modifiers, key):
                    self.registered.append(hotkey_id)

    def nativeEventFilter(self, event_type, message):
        if os.name == "nt" and event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam in self.bindings:
                self.bindings[msg.wParam][1]()
                return True, 0
        return False, 0

    def unregister(self) -> None:
        if os.name == "nt":
            for hotkey_id in self.registered:
                ctypes.windll.user32.UnregisterHotKey(self.window_handle, hotkey_id)
        self.registered.clear()

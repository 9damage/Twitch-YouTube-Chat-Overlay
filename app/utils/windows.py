from __future__ import annotations

import os
import sys
from collections.abc import Callable

if os.name == "nt":
    import ctypes
    import winreg
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 1, 2, 4, 8
    WM_HOTKEY = 0x0312
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t


def set_click_through(hwnd: int, enabled: bool) -> None:
    if os.name != "nt":
        return
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED
    style = style | WS_EX_TRANSPARENT if enabled else style & ~WS_EX_TRANSPARENT
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def set_startup(enabled: bool, executable: str) -> None:
    if os.name != "nt":
        return
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "ChatOverlay", 0, winreg.REG_SZ, f'"{executable}"')
        else:
            try:
                winreg.DeleteValue(key, "ChatOverlay")
            except FileNotFoundError:
                return


def parse_hotkey(sequence: str) -> tuple[int, int]:
    if os.name != "nt":
        return 0, 0
    parts = [part.strip().upper() for part in sequence.split("+")]
    modifiers = 0
    mapping = {"ALT": MOD_ALT, "CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL, "SHIFT": MOD_SHIFT, "WIN": MOD_WIN}
    for part in parts[:-1]:
        modifiers |= mapping.get(part, 0)
    key = parts[-1]
    vk = ord(key) if len(key) == 1 else getattr(wintypes, f"VK_{key}", 0)
    return modifiers, vk


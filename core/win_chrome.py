"""Windows-only helpers to give a frameless QWidget the native features
of a regular window (Aero Snap, Win+arrow shortcuts, drag-to-edge tile preview)
without showing any OS chrome.

The trick: keep `Qt.FramelessWindowHint`, but add `WS_THICKFRAME`,
`WS_MAXIMIZEBOX`, `WS_MINIMIZEBOX` to the Win32 window style. Aero Snap
needs these to engage. Then we eat `WM_NCCALCSIZE` so Windows doesn't
draw any non-client frame — the window stays visually frameless while
behaving like a native window for the OS.

No-op on platforms other than Windows.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    _user32 = ctypes.windll.user32

    GWL_STYLE      = -16
    WS_THICKFRAME  = 0x00040000
    WS_MAXIMIZEBOX = 0x00010000
    WS_MINIMIZEBOX = 0x00020000
    WS_SYSMENU     = 0x00080000

    WM_NCCALCSIZE  = 0x0083

    # SetWindowLongPtrW is the 64-bit safe variant; falls back on 32-bit Python.
    if hasattr(_user32, "SetWindowLongPtrW"):
        _GetWindowLong = _user32.GetWindowLongPtrW
        _SetWindowLong = _user32.SetWindowLongPtrW
        _GetWindowLong.restype = ctypes.c_longlong
        _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
        _SetWindowLong.restype = ctypes.c_longlong
        _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
    else:
        _GetWindowLong = _user32.GetWindowLongW
        _SetWindowLong = _user32.SetWindowLongW


def enable_native_features(widget) -> bool:
    """Add Aero-Snap-friendly Win32 styles to a frameless widget. Idempotent.

    Returns True if features were enabled (Windows only).
    """
    if not _IS_WIN:
        return False
    hwnd = int(widget.winId())
    style = _GetWindowLong(hwnd, GWL_STYLE)
    new_style = style | WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU
    if new_style != style:
        _SetWindowLong(hwnd, GWL_STYLE, new_style)
    return True


def is_nccalcsize(eventType, message) -> bool:
    """True when a Qt nativeEvent matches the WM_NCCALCSIZE window message.

    Calling code should return ``True, 0`` from ``nativeEvent`` to tell
    Windows the entire window is client area (no non-client frame drawn).
    """
    if not _IS_WIN or eventType != b"windows_generic_MSG":
        return False
    msg = wintypes.MSG.from_address(int(message))
    return msg.message == WM_NCCALCSIZE

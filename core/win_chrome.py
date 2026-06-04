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
    WS_MAXIMIZE    = 0x01000000

    WM_NCCALCSIZE  = 0x0083
    WM_SYSCOMMAND  = 0x0112
    SC_MAXIMIZE    = 0xF030
    SC_RESTORE     = 0xF120

    MONITOR_DEFAULTTONEAREST = 2

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

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("rcMonitor", _RECT), ("rcWork", _RECT),
                    ("dwFlags", wintypes.DWORD)]


def toggle_maximize(widget) -> None:
    """Maximize or restore a window via Win32 WM_SYSCOMMAND (posted asynchronously).

    PostMessageW defers the command until after all pending mouse events are
    processed, avoiding state-change races during click handling. Falls back
    to Qt on non-Windows.
    """
    if not _IS_WIN:
        if widget.isMaximized():
            widget.showNormal()
        else:
            widget.showMaximized()
        return
    hwnd = int(widget.winId())
    style = _GetWindowLong(hwnd, GWL_STYLE)
    cmd = SC_RESTORE if (style & WS_MAXIMIZE) else SC_MAXIMIZE
    _user32.PostMessageW(hwnd, WM_SYSCOMMAND, cmd, 0)


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


def handle_nccalcsize(eventType, message):
    """Handle WM_NCCALCSIZE for a frameless window.

    Returns ``(True, 0)`` to eliminate the NC frame. When the window is
    maximized the proposed client rect is clamped to the monitor's work area
    so the taskbar stays accessible. Returns ``None`` for unrelated events.
    """
    if not _IS_WIN or eventType != b"windows_generic_MSG":
        return None
    msg = wintypes.MSG.from_address(int(message))
    if msg.message != WM_NCCALCSIZE:
        return None

    hwnd = msg.hWnd
    if msg.wParam and hwnd:
        style = _GetWindowLong(hwnd, GWL_STYLE)
        if style & WS_MAXIMIZE:
            proposed = _RECT.from_address(msg.lParam)
            monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            _user32.GetMonitorInfoW(monitor, ctypes.byref(mi))
            full = mi.rcMonitor
            # Only clamp when Windows is proposing the full monitor rect (maximize).
            # During a restore, the proposed rect is the normal window geometry
            # (smaller than the monitor) — clamping there would block the restore.
            if (proposed.left <= full.left and proposed.top <= full.top
                    and proposed.right >= full.right
                    and proposed.bottom >= full.bottom):
                proposed.left   = mi.rcWork.left
                proposed.top    = mi.rcWork.top
                proposed.right  = mi.rcWork.right
                proposed.bottom = mi.rcWork.bottom

    return True, 0

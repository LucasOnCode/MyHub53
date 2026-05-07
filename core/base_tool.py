"""BaseTool — common shell for every MyHub53 tool window (PySide6).

A frameless top-level QWidget that hosts:
  * a custom title bar with drag (startSystemMove) + close button,
  * a background widget chosen by `univers` (aquatic / parchment / velvet),
  * a body container the subclass populates via `build()`.

Subclasses must override `build()` and add widgets to `self.body_layout`.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import theme
from core.win_chrome import enable_native_features, is_nccalcsize


class _ToolTitleBar(QFrame):
    close_clicked = Signal()

    def __init__(self, name: str, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolTitleBar")
        self.setFixedHeight(46)
        self.setStyleSheet(f"""
            #ToolTitleBar {{
                background-color: {theme.rgba(theme.INK_DEEP, 0.55)};
                border-top-left-radius: 0;
                border-top-right-radius: 0;
                border-bottom: 1px solid {theme.rgba(accent, 0.30)};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 10, 0)
        layout.setSpacing(12)

        accent_bar = QFrame()
        accent_bar.setFixedSize(3, 22)
        accent_bar.setStyleSheet(
            f"background-color: {accent}; border-radius: 1px; border: none;"
        )
        layout.addWidget(accent_bar)

        self.title_lbl = QLabel(name)
        self.title_lbl.setFont(theme.font("display", 16, QFont.Weight.Medium))
        self.title_lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        layout.addWidget(self.title_lbl)

        layout.addStretch(1)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(theme.qss_close_btn())
        self.close_btn.clicked.connect(self.close_clicked)
        layout.addWidget(self.close_btn)

    # Delegate drag to the OS so we get Aero Snap previews.
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemMove():
                e.accept()
                return
        super().mousePressEvent(e)


class BaseTool(QWidget):
    statusChanged = Signal(str, object)  # text, color (str | None)

    def __init__(self,
                 parent: QWidget | None = None,
                 *,
                 name: str,
                 accent: str,
                 univers: str = "aquatic",
                 width: int = 760,
                 height: int = 720,
                 min_w: int = 620,
                 min_h: int = 520) -> None:
        super().__init__(parent)
        self.tool_name = name
        self.accent = accent
        self.univers = univers
        self._native_chrome_done = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Window)
        self.setWindowTitle(name)
        self.setMinimumSize(min_w, min_h)
        self.resize(width, height)

        self._center_over(parent, width, height)

        # Background — painted by the chosen univers.
        self.bg: QWidget | None = self._make_bg(univers)
        if self.bg is not None:
            self.bg.setParent(self)
            self.bg.setGeometry(0, 0, width, height)
            self.bg.lower()

        # Title bar + body container.
        self.titlebar = _ToolTitleBar(name, accent, self)
        self.titlebar.close_clicked.connect(self.close)

        self.body = QWidget(self)
        self.body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(24, 16, 24, 16)
        self.body_layout.setSpacing(12)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.titlebar)
        outer.addWidget(self.body, stretch=1)

        self._status_label: Optional[QLabel] = None
        self.statusChanged.connect(self._apply_status)

        # Hand off to subclass — it adds its UI to self.body_layout.
        self.build()

    # ── Hooks for subclasses ─────────────────────────────────────────────────
    def build(self) -> None:
        raise NotImplementedError("Tool must implement build()")

    # ── Status bar (thread-safe via signal) ──────────────────────────────────
    def _make_status_bar(self, initial: str = "Prêt") -> QLabel:
        self._status_label = QLabel(initial)
        self._status_label.setFont(
            theme.font("body", 11, QFont.Weight.DemiBold, letter_spacing=4)
        )
        self._status_label.setStyleSheet(
            f"color: {theme.FG_MUTED}; background: transparent;"
            f"padding-top: 4px;"
        )
        self.body_layout.addWidget(self._status_label)
        return self._status_label

    def set_status(self, msg: str, color: Optional[str] = None) -> None:
        """Safe to call from any thread — Qt queues it to the UI thread."""
        self.statusChanged.emit(msg, color)

    def _apply_status(self, msg, color) -> None:
        if self._status_label is None:
            return
        c = color or theme.FG_MUTED
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(
            f"color: {c}; background: transparent; padding-top: 4px;"
        )

    # ── Background factory ───────────────────────────────────────────────────
    def _make_bg(self, univers: str) -> QWidget | None:
        if univers == "aquatic":
            from core.aquatic_bg import AquaticBg
            return AquaticBg()
        # parchment / velvet land in a later step; for now fall back to None
        # which means the dialog will inherit Qt's default flat colour.
        return None

    # ── Geometry ─────────────────────────────────────────────────────────────
    def _center_over(self, parent: QWidget | None, w: int, h: int) -> None:
        if parent is not None:
            geo = parent.frameGeometry()
            x = geo.x() + (geo.width() - w) // 2
            y = geo.y() + (geo.height() - h) // 2
        else:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            avail = screen.availableGeometry()
            x = avail.x() + (avail.width() - w) // 2
            y = avail.y() + (avail.height() - h) // 2
        self.move(max(0, x), max(0, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.bg is not None:
            self.bg.setGeometry(0, 0, self.width(), self.height())

    # ── Native Win32 chrome (Aero Snap, Win+arrow shortcuts) ─────────────────
    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_chrome_done:
            enable_native_features(self)
            self._native_chrome_done = True

    def nativeEvent(self, eventType, message):
        if is_nccalcsize(eventType, message):
            return True, 0
        return super().nativeEvent(eventType, message)

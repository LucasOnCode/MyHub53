"""Static painted background for the MyHub53 hub.

Recreates the .atmos layer from design/styles.css: a deep-blue vertical base
with three colored radial blobs (iris top-left, turquoise top-right, framboise
bottom). No animation in this step — the drift/shimmer come later.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget


class AtmosBg(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#161a3a"))
        base.setColorAt(0.6, QColor("#0a0d1f"))
        base.setColorAt(1.0, QColor("#050714"))
        p.fillRect(0, 0, w, h, base)

        blobs = (
            (0.20, 0.00, 0.85, QColor(155,  94, 219, int(0.45 * 255))),
            (0.90, 0.30, 0.75, QColor( 95, 200, 216, int(0.40 * 255))),
            (0.50, 1.00, 0.90, QColor(232,  77, 111, int(0.28 * 255))),
        )
        for cx_pct, cy_pct, r_pct, color in blobs:
            cx, cy = w * cx_pct, h * cy_pct
            r = max(w, h) * r_pct
            grad = QRadialGradient(QPointF(cx, cy), r)
            grad.setColorAt(0.0, color)
            transparent = QColor(color)
            transparent.setAlpha(0)
            grad.setColorAt(0.7, transparent)
            p.fillRect(0, 0, w, h, grad)

        p.end()

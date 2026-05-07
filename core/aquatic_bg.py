"""AquaticBg — animated underwater background for the 'aquatic' univers.

A dark blue base gradient with slowly drifting caustic blobs and a layer
of small turquoise bubbles rising. The whole layer is mouse-transparent
so it never blocks UI events above it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget


@dataclass
class _Bubble:
    x: float
    y: float
    size: float
    speed: float
    sway_amp: float
    sway_phase: float


@dataclass
class _Caustic:
    cx: float        # in 0..1 (relative to width)
    cy: float        # in 0..1
    rx: float        # ellipse radius x in 0..1
    ry: float        # ellipse radius y in 0..1
    alpha: int       # 0..255
    drift_amp: float
    drift_phase: float


class AquaticBg(QWidget):
    """Static gradient + animated caustics + rising bubbles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)

        self._t = 0.0
        self._dt = 1.0 / 30.0  # 30 fps is plenty for slow caustics

        # Three caustic blobs at fixed-ish positions, sized in % of widget.
        self._caustics: List[_Caustic] = [
            _Caustic(0.25, 0.30, 0.45, 0.22, int(0.18 * 255), 0.04, 0.0),
            _Caustic(0.70, 0.60, 0.50, 0.24, int(0.14 * 255), 0.05, 1.7),
            _Caustic(0.50, 0.92, 0.55, 0.20, int(0.16 * 255), 0.04, 3.4),
        ]

        self._bubbles: List[_Bubble] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 * self._dt))

    # ── Population ───────────────────────────────────────────────────────────
    def _ensure_bubbles(self) -> None:
        if self._bubbles or self.width() <= 0 or self.height() <= 0:
            return
        for _ in range(18):
            self._bubbles.append(self._spawn_bubble(initial=True))

    def _spawn_bubble(self, *, initial: bool) -> _Bubble:
        w = max(1, self.width())
        h = max(1, self.height())
        return _Bubble(
            x=random.uniform(0, w),
            y=random.uniform(0, h) if initial else h + random.uniform(0, h * 0.2),
            size=random.uniform(2.0, 5.0),
            speed=random.uniform(0.3, 1.0),
            sway_amp=random.uniform(6, 16),
            sway_phase=random.uniform(0, math.tau),
        )

    # ── Animation tick ───────────────────────────────────────────────────────
    def _tick(self) -> None:
        self._ensure_bubbles()
        if self._bubbles:
            for b in self._bubbles:
                b.y -= b.speed
                if b.y < -b.size * 2:
                    fresh = self._spawn_bubble(initial=False)
                    b.x, b.y = fresh.x, fresh.y
                    b.size = fresh.size
                    b.speed = fresh.speed
                    b.sway_amp = fresh.sway_amp
                    b.sway_phase = fresh.sway_phase
        self._t += self._dt
        self.update()

    # ── Painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # Base vertical gradient — deep blue to near-black.
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#1d2455"))
        base.setColorAt(0.55, QColor("#0e1338"))
        base.setColorAt(1.0, QColor("#060920"))
        p.fillRect(0, 0, w, h, base)

        # Top accent — a softer iris/blue glow at the top.
        top = QRadialGradient(QPointF(w * 0.30, 0), max(w, h) * 0.7)
        top.setColorAt(0.0, QColor(80, 110, 200, int(0.55 * 255)))
        top.setColorAt(0.7, QColor(80, 110, 200, 0))
        p.fillRect(0, 0, w, h, top)

        # Animated caustics — turquoise blobs that drift slowly.
        for c in self._caustics:
            cx = (c.cx + math.sin(self._t * 0.3 + c.drift_phase) * c.drift_amp) * w
            cy = (c.cy + math.cos(self._t * 0.25 + c.drift_phase) * c.drift_amp) * h
            rx = c.rx * w
            ry = c.ry * h
            radius = max(rx, ry)
            grad = QRadialGradient(QPointF(cx, cy), radius)
            grad.setColorAt(0.0, QColor(110, 220, 230, c.alpha))
            grad.setColorAt(0.7, QColor(110, 220, 230, 0))
            p.fillRect(0, 0, w, h, grad)

        # Rising bubbles — small radial gradients.
        if self._bubbles:
            p.setPen(Qt.PenStyle.NoPen)
            for b in self._bubbles:
                x = b.x + math.sin(self._t * 0.6 + b.sway_phase) * b.sway_amp
                # Fade in from bottom, fade out near top.
                fade_in = min(1.0, max(0.0, (h - b.y) / (h * 0.10)))
                fade_out = min(1.0, max(0.0, b.y / (h * 0.12)))
                alpha = min(fade_in, fade_out)
                if alpha <= 0:
                    continue
                radius = b.size * 2.0
                grad = QRadialGradient(QPointF(x, b.y), radius)
                grad.setColorAt(0.0, QColor(220, 245, 250, int(220 * alpha)))
                grad.setColorAt(0.5, QColor(110, 220, 230, int(80 * alpha)))
                grad.setColorAt(1.0, QColor(110, 220, 230, 0))
                p.setBrush(grad)
                p.drawEllipse(QPointF(x, b.y), radius, radius)

        p.end()

    def resizeEvent(self, _event):
        # Keep bubbles within bounds when the layer shrinks.
        w = max(1, self.width())
        for b in self._bubbles:
            if b.x > w:
                b.x = random.uniform(0, w)
        if not self._bubbles:
            self._ensure_bubbles()

"""Animated effects layered over the hub.

`ParticleLayer` is a transparent overlay that paints floating particles
drifting from the bottom of the screen to the top, with a gentle
horizontal sway. Mouse-transparent so it never blocks clicks below.

Inspired by the .particles / .particle CSS in design/styles.css.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget


# RGB triplets approximating the design's oklch hues.
PARTICLE_COLORS: list[tuple[int, int, int]] = [
    (95, 200, 216),    # turquoise   (oklch hue ~195)
    (232, 77, 111),    # framboise   (oklch hue ~5)
    (155, 94, 219),    # iris        (oklch hue ~305)
]


@dataclass
class _Particle:
    x: float
    y: float
    size: float       # 2.5–7 px radius
    speed: float      # px per frame upward
    sway_amp: float   # horizontal sway amplitude in px
    sway_phase: float
    color_idx: int


class ParticleLayer(QWidget):
    """Animated overlay of floating particles."""

    def __init__(self,
                 parent: QWidget | None = None,
                 density: int = 28,
                 fps: int = 60) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._density = density
        self._t = 0.0
        self._dt = 1.0 / fps
        self._particles: List[_Particle] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / fps))

    # ── Spawning ─────────────────────────────────────────────────────────────
    def _spawn(self, *, initial: bool = False) -> _Particle:
        w = max(1, self.width())
        h = max(1, self.height())
        size = random.uniform(2.5, 7.0)
        return _Particle(
            x=random.uniform(0, w),
            y=random.uniform(0, h) if initial else h + random.uniform(0, h * 0.25),
            size=size,
            speed=random.uniform(0.4, 1.6),
            sway_amp=random.uniform(8, 26),
            sway_phase=random.uniform(0, math.tau),
            color_idx=random.randint(0, len(PARTICLE_COLORS) - 1),
        )

    def _ensure_population(self) -> None:
        if not self._particles and self.width() > 0 and self.height() > 0:
            self._particles = [self._spawn(initial=True) for _ in range(self._density)]

    # ── Animation tick ───────────────────────────────────────────────────────
    def _tick(self) -> None:
        self._ensure_population()
        if not self._particles:
            return
        self._t += self._dt
        for p in self._particles:
            p.y -= p.speed
            if p.y < -p.size * 2:
                fresh = self._spawn(initial=False)
                p.x = fresh.x
                p.y = fresh.y
                p.size = fresh.size
                p.speed = fresh.speed
                p.sway_amp = fresh.sway_amp
                p.sway_phase = fresh.sway_phase
                p.color_idx = fresh.color_idx
        self.update()

    # ── Painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        if not self._particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        h = max(1.0, float(self.height()))
        for p in self._particles:
            x = p.x + math.sin(self._t * 0.6 + p.sway_phase) * p.sway_amp
            # Fade in from bottom, fade out near top.
            fade_in  = min(1.0, max(0.0, (h - p.y) / (h * 0.10)))
            fade_out = min(1.0, max(0.0, p.y / (h * 0.15)))
            alpha = min(fade_in, fade_out)
            if alpha <= 0.0:
                continue

            r, g, b = PARTICLE_COLORS[p.color_idx]
            radius = p.size * 2.2
            grad = QRadialGradient(QPointF(x, p.y), radius)
            grad.setColorAt(0.0, QColor(min(255, r + 60), min(255, g + 60), min(255, b + 60),
                                         int(220 * alpha)))
            grad.setColorAt(0.5, QColor(r, g, b, int(80 * alpha)))
            grad.setColorAt(1.0, QColor(r, g, b, 0))
            painter.setBrush(grad)
            painter.drawEllipse(QPointF(x, p.y), radius, radius)
        painter.end()

    # ── Resize handling ──────────────────────────────────────────────────────
    def resizeEvent(self, _event):
        # On first resize after construction we can finally seed particles.
        self._ensure_population()
        # Keep existing particles in bounds when the layer shrinks.
        w = max(1, self.width())
        for p in self._particles:
            if p.x > w:
                p.x = random.uniform(0, w)

    # ── Public controls ──────────────────────────────────────────────────────
    def set_running(self, running: bool) -> None:
        if running and not self._timer.isActive():
            self._timer.start()
        elif not running and self._timer.isActive():
            self._timer.stop()

    def set_density(self, density: int) -> None:
        self._density = max(0, density)
        self._particles = []
        self._ensure_population()

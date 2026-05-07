"""Visual smoke-test for core/theme.py.

Run from the project root:
    venv\\Scripts\\python.exe scripts\\test_theme.py

Verifies that fonts load, QSS applies, and that the three semantic font roles
render correctly (Fraunces display italic, Quicksand body, JetBrains mono).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `core.theme` importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import theme


def labeled(text: str, fnt: QFont) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(fnt)
    return lbl


def main() -> int:
    app = QApplication(sys.argv)
    loaded = theme.load_fonts()
    print(f"[theme] loaded families: {sorted(loaded)}")
    app.setStyleSheet(theme.qss_app())

    win = QWidget()
    win.setWindowTitle("MyHub53 — theme smoke test")
    win.resize(640, 540)

    root = QVBoxLayout(win)
    root.setContentsMargins(40, 32, 40, 32)
    root.setSpacing(18)

    # Display title (Fraunces italic)
    root.addWidget(
        labeled(
            "Onirique aquatique impressionniste",
            theme.font("display", 32, QFont.Weight.Light, italic=True),
        )
    )

    # Body paragraph (Quicksand)
    body = labeled(
        "Quicksand body — chaque outil dérive d'une même palette,\n"
        "mais s'incarne dans son propre univers visuel.",
        theme.font("body", 14, QFont.Weight.Normal),
    )
    body.setStyleSheet(f"color: {theme.FG_MUTED};")
    root.addWidget(body)

    # Mono line (JetBrains Mono)
    mono = labeled("v1.0.0  ·  build 2026.05  ·  release-channel: stable",
                   theme.font("mono", 12, QFont.Weight.Medium))
    mono.setStyleSheet(f"color: {theme.TURQUOISE};")
    root.addWidget(mono)

    # Input
    inp = QLineEdit()
    inp.setPlaceholderText("Colle ici une URL YouTube…")
    inp.setStyleSheet(theme.qss_input())
    inp.setMinimumHeight(46)
    root.addWidget(inp)

    # Buttons row: primary + ghost + close
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)

    btn_primary = QPushButton("✦  Lancer l'analyse")
    btn_primary.setStyleSheet(theme.qss_button_primary())
    btn_primary.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_row.addWidget(btn_primary)

    btn_ghost = QPushButton("Annuler")
    btn_ghost.setStyleSheet(theme.qss_button_ghost())
    btn_ghost.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_row.addWidget(btn_ghost)

    btn_close = QPushButton("✕")
    btn_close.setFixedSize(36, 36)
    btn_close.setStyleSheet(theme.qss_close_btn())
    btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_row.addWidget(btn_close)

    btn_row.addStretch(1)
    root.addLayout(btn_row)

    # Pills row (active + inactive)
    pills_row = QHBoxLayout()
    pills_row.setSpacing(6)
    for label, active in [("MP3", True), ("FLAC", False), ("M4A", False),
                          ("WAV", False), ("OGG", False)]:
        p = QPushButton(label)
        p.setStyleSheet(theme.qss_pill(active=active))
        p.setCursor(Qt.CursorShape.PointingHandCursor)
        pills_row.addWidget(p)
    pills_row.addStretch(1)
    root.addLayout(pills_row)

    # Header-like row: version pill + update badge
    head_row = QHBoxLayout()
    head_row.setSpacing(10)

    version = QLabel("v1.0.0")
    version.setStyleSheet(theme.qss_version_pill())
    head_row.addWidget(version)

    badge = QPushButton("▲ v1.1.0 dispo")
    badge.setStyleSheet(theme.qss_update_badge())
    badge.setCursor(Qt.CursorShape.PointingHandCursor)
    head_row.addWidget(badge)

    head_row.addStretch(1)
    root.addLayout(head_row)

    # Color swatch strip — visual sanity check for each token
    swatch_row = QHBoxLayout()
    swatch_row.setSpacing(8)
    for name, color in [
        ("ink", theme.INK),
        ("turq", theme.TURQUOISE),
        ("framb", theme.FRAMBOISE),
        ("iris", theme.IRIS),
        ("gold", theme.GOLD),
        ("paper", theme.PAPER),
    ]:
        chip = QFrame()
        chip.setFixedSize(72, 36)
        chip.setStyleSheet(
            f"background-color: {color}; border-radius: 8px;"
            f"border: 1px solid {theme.rgba(theme.PAPER, 0.15)};"
        )
        chip.setToolTip(f"{name} = {color}")
        swatch_row.addWidget(chip)
    swatch_row.addStretch(1)
    root.addLayout(swatch_row)

    root.addStretch(1)

    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

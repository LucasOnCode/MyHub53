"""MyHub53 — design tokens and Qt theming.

Single source of truth for colors, spacing, fonts, and QSS used by every
PySide6 widget in the project. Imported as `from core import theme`.

Color tokens are hex approximations of the oklch values defined in
design/styles.css (the HTML mockup is the visual reference).
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from typing import Literal

from PySide6.QtGui import QFont, QFontDatabase

# ─────────────────────────────────────────────────────────────────────────────
# Color tokens (hex from oklch — see design/MIGRATION.md)
# ─────────────────────────────────────────────────────────────────────────────

INK_DEEPEST    = "#0a0d1f"
INK_DEEP       = "#161a3a"
INK            = "#1f2858"
INK_MID        = "#2e3a78"
INK_SOFT       = "#4a5896"

TURQUOISE      = "#5fc8d8"
TURQUOISE_DEEP = "#2a9bb0"
FRAMBOISE      = "#e84d6f"
FRAMBOISE_SOFT = "#f08aa0"
IRIS           = "#9b5edb"
IRIS_SOFT      = "#b890e8"

GOLD           = "#d4b378"
GOLD_DEEP      = "#a88a55"
PAPER          = "#f5f1e8"
PAPER_WARM     = "#ebe2cf"

FG             = "#f5f3ee"
FG_MUTED       = "#a5b0d0"
FG_DIM         = "#7080a8"

# Status colors (kept similar to current tkinter palette for continuity)
SUCCESS        = "#22d3a5"
ERROR          = "#ef4444"
WARNING        = "#f59e0b"


# ─────────────────────────────────────────────────────────────────────────────
# Geometry tokens
# ─────────────────────────────────────────────────────────────────────────────

RADIUS_TILE    = 22
RADIUS_CARD    = 14
RADIUS_BTN     = 12
RADIUS_INPUT   = 14
RADIUS_PILL    = 999

PAD_TILE       = 22
PAD_SECTION    = 44
GAP_GRID       = 18
GAP_FORM       = 10


# ─────────────────────────────────────────────────────────────────────────────
# Typography tokens
# ─────────────────────────────────────────────────────────────────────────────

FONT_BODY      = "Quicksand"
FONT_DISPLAY   = "Fraunces"
FONT_MONO      = "JetBrains Mono"

# Fallback when a TTF could not be loaded (e.g. dev without assets/fonts/).
FONT_FALLBACK  = "Segoe UI"

_loaded_families: set[str] = set()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def resource_path(rel: str) -> str:
    """Return absolute path to a resource, working in dev and PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / rel)


def rgba(hex_color: str, alpha: float) -> str:
    """Convert '#RRGGBB' + alpha[0..1] to a Qt-friendly 'rgba(r,g,b,a)' string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = max(0.0, min(1.0, alpha))
    return f"rgba({r}, {g}, {b}, {a:.3f})"


def load_fonts() -> set[str]:
    """Register all TTFs from assets/fonts/ with Qt. Idempotent.

    Must be called after a QApplication exists. Returns the set of family
    names successfully made available. Missing families fall back silently
    to FONT_FALLBACK so the app never crashes on a broken font file.
    """
    fonts_dir = Path(resource_path("assets/fonts"))
    if not fonts_dir.is_dir():
        warnings.warn(f"[theme] fonts dir not found: {fonts_dir}", stacklevel=2)
        return set()

    for ttf in sorted(fonts_dir.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(ttf))
        if font_id == -1:
            warnings.warn(f"[theme] failed to load font: {ttf.name}", stacklevel=2)
            continue
        for fam in QFontDatabase.applicationFontFamilies(font_id):
            _loaded_families.add(fam)

    available = set(QFontDatabase.families())
    for needed in (FONT_BODY, FONT_DISPLAY, FONT_MONO):
        if needed not in available:
            warnings.warn(
                f"[theme] family '{needed}' not available — falling back to {FONT_FALLBACK}",
                stacklevel=2,
            )
    return _loaded_families


def _resolve_family(role: Literal["body", "display", "mono"]) -> str:
    requested = {"body": FONT_BODY, "display": FONT_DISPLAY, "mono": FONT_MONO}[role]
    return requested if requested in QFontDatabase.families() else FONT_FALLBACK


def font(
    role: Literal["body", "display", "mono"] = "body",
    size: int = 13,
    weight: int = QFont.Weight.Medium,
    italic: bool = False,
    letter_spacing: float | None = None,
) -> QFont:
    """Build a QFont for one of the three semantic roles."""
    f = QFont(_resolve_family(role), size)
    f.setWeight(QFont.Weight(weight))
    f.setItalic(italic)
    if letter_spacing is not None:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100 + letter_spacing)
    return f


# ─────────────────────────────────────────────────────────────────────────────
# QSS generators
# ─────────────────────────────────────────────────────────────────────────────

def qss_app() -> str:
    """Global stylesheet — set on the QApplication once at startup."""
    return f"""
    * {{
        color: {FG};
        selection-background-color: {rgba(TURQUOISE, 0.35)};
        selection-color: {FG};
    }}
    QToolTip {{
        background-color: {INK_DEEP};
        color: {FG};
        border: 1px solid {rgba(TURQUOISE, 0.3)};
        padding: 6px 10px;
        border-radius: {RADIUS_BTN}px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {rgba(TURQUOISE, 0.30)};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {rgba(TURQUOISE, 0.50)};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {rgba(TURQUOISE, 0.30)};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {rgba(TURQUOISE, 0.50)};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """


def qss_button_primary(c1: str = TURQUOISE, c2: str = IRIS) -> str:
    return f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 {c1}, stop:1 {c2});
        color: {INK_DEEPEST};
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-weight: 700;
        font-size: 13px;
        padding: 12px 22px;
        border: none;
        border-radius: {RADIUS_INPUT}px;
        letter-spacing: 0.5px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 {c2}, stop:1 {c1});
    }}
    QPushButton:disabled {{
        color: {rgba(INK_DEEPEST, 0.6)};
        background: {rgba(c1, 0.4)};
    }}
    """


def qss_button_ghost() -> str:
    return f"""
    QPushButton {{
        background-color: {rgba(INK, 0.5)};
        border: 1px solid {rgba(TURQUOISE, 0.25)};
        color: {FG_MUTED};
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-weight: 600;
        font-size: 13px;
        padding: 12px 22px;
        border-radius: {RADIUS_INPUT}px;
    }}
    QPushButton:hover {{
        color: {FG};
        border-color: {TURQUOISE};
    }}
    QPushButton:disabled {{
        color: {rgba(FG_MUTED, 0.5)};
    }}
    """


def qss_input() -> str:
    return f"""
    QLineEdit {{
        background-color: {rgba(INK_DEEPEST, 0.6)};
        border: 1px solid {rgba(TURQUOISE, 0.30)};
        border-radius: {RADIUS_INPUT}px;
        color: {FG};
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-size: 14px;
        padding: 12px 16px;
        selection-background-color: {rgba(TURQUOISE, 0.4)};
    }}
    QLineEdit:focus {{
        border: 1px solid {TURQUOISE};
    }}
    QLineEdit:disabled {{
        color: {FG_DIM};
    }}
    """


def qss_pill(active: bool = False) -> str:
    if active:
        return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 {TURQUOISE}, stop:1 {IRIS});
            color: {INK_DEEPEST};
            border: 1px solid transparent;
            border-radius: {RADIUS_PILL}px;
            padding: 6px 16px;
            min-width: 40px;
            font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
            font-weight: 700;
            font-size: 11px;
        }}
        """
    return f"""
    QPushButton {{
        background-color: {rgba(INK, 0.5)};
        border: 1px solid {rgba(TURQUOISE, 0.18)};
        color: {FG_MUTED};
        border-radius: {RADIUS_PILL}px;
        padding: 6px 16px;
        min-width: 40px;
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-weight: 600;
        font-size: 11px;
    }}
    QPushButton:hover {{
        color: {FG};
        border-color: {rgba(TURQUOISE, 0.4)};
    }}
    """


def qss_close_btn() -> str:
    return f"""
    QPushButton {{
        background-color: {rgba(INK_DEEPEST, 0.4)};
        border: 1px solid {rgba(PAPER, 0.2)};
        color: {FG};
        border-radius: 18px;
        font-size: 14px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        background-color: {rgba(FRAMBOISE, 0.4)};
        border-color: {FRAMBOISE};
    }}
    """


def qss_version_pill() -> str:
    return f"""
    QLabel {{
        background-color: {rgba(INK_DEEPEST, 0.5)};
        border: 1px solid {rgba(TURQUOISE, 0.25)};
        color: {FG_MUTED};
        border-radius: {RADIUS_PILL}px;
        padding: 4px 12px;
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    """


def qss_update_badge() -> str:
    return f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 {TURQUOISE}, stop:1 {IRIS});
        color: {INK_DEEPEST};
        border: none;
        border-radius: {RADIUS_PILL}px;
        padding: 8px 14px;
        font-family: "{FONT_BODY}", "{FONT_FALLBACK}";
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.4px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 {IRIS}, stop:1 {TURQUOISE});
    }}
    """

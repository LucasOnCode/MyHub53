"""Hub widgets — header, hero, category tile, recent tile, placeholder dialog.

All widgets here are static (no animations): suitable for step 2 of the
PySide6 migration. Animations land in step 3 (particles) and step 4
(category tile hover).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core import theme
from tools.registry import Category, ToolCard


# ─────────────────────────────────────────────────────────────────────────────
# Brand mark (52×52 jewel with conic gradient ring) — drawn entirely with QPainter
# ─────────────────────────────────────────────────────────────────────────────

class BrandMark(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        grad = QRadialGradient(rect.left() + rect.width() * 0.3,
                               rect.top() + rect.height() * 0.3,
                               rect.width() * 0.9)
        grad.setColorAt(0.0, QColor(theme.TURQUOISE))
        grad.setColorAt(0.6, QColor(theme.INK))
        grad.setColorAt(1.0, QColor(theme.IRIS))
        p.fillPath(path, QBrush(grad))

        # subtle inner highlight
        pen = QPen(QColor(245, 241, 232, 64), 1.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 14, 14)

        # "M" letter
        p.setPen(QColor(theme.PAPER))
        p.setFont(theme.font("display", 22, QFont.Weight.Bold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "M")
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Header bar — drag, brand, version, update badge, settings/min/close buttons
# ─────────────────────────────────────────────────────────────────────────────

class HeaderBar(QFrame):
    update_clicked = Signal()
    settings_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(86)
        self.setStyleSheet(self._qss())
        self._drag_offset: Optional[QPointF] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(14)

        # Brand
        brand = QHBoxLayout()
        brand.setSpacing(14)
        brand.addWidget(BrandMark())

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        name = QLabel("MyHub53")
        name.setFont(theme.font("display", 22, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        tag = QLabel("BOÎTE À MERVEILLES")
        tag.setFont(theme.font("body", 10, QFont.Weight.Medium, letter_spacing=4))
        tag.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        text_col.addWidget(name)
        text_col.addWidget(tag)
        brand.addLayout(text_col)
        layout.addLayout(brand)

        layout.addStretch(1)

        # Update badge (hidden until check completes positively)
        self.update_btn = QPushButton(f"▲ Mise à jour disponible")
        self.update_btn.setStyleSheet(theme.qss_update_badge())
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.hide()
        self.update_btn.clicked.connect(self.update_clicked)
        layout.addWidget(self.update_btn)

        # Version pill
        self.version_label = QLabel(f"v{version}")
        self.version_label.setStyleSheet(theme.qss_version_pill())
        self.version_label.setFont(theme.font("body", 11, QFont.Weight.DemiBold))
        layout.addWidget(self.version_label)

        # Icon buttons (settings, minimize, close)
        self.settings_btn = self._make_icon_btn("⚙", "Paramètres")
        self.settings_btn.clicked.connect(self.settings_clicked)
        layout.addWidget(self.settings_btn)

        self.min_btn = self._make_icon_btn("—", "Réduire")
        self.min_btn.clicked.connect(self.minimize_clicked)
        layout.addWidget(self.min_btn)

        self.max_btn = self._make_icon_btn("◻", "Agrandir")
        self.max_btn.clicked.connect(self.maximize_clicked)
        layout.addWidget(self.max_btn)

        self.close_btn = self._make_icon_btn("✕", "Fermer", danger=True)
        self.close_btn.clicked.connect(self.close_clicked)
        layout.addWidget(self.close_btn)

    @staticmethod
    def _qss() -> str:
        return f"""
        #HeaderBar {{
            background-color: {theme.rgba(theme.INK_DEEP, 0.7)};
            border: 1px solid {theme.rgba(theme.TURQUOISE, 0.22)};
            border-radius: 20px;
        }}
        """

    def _make_icon_btn(self, glyph: str, tooltip: str, danger: bool = False) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setFixedSize(38, 38)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(theme.font("body", 13, QFont.Weight.DemiBold))
        hover_color = theme.FRAMBOISE if danger else theme.TURQUOISE
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.rgba(theme.INK, 0.5)};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.20)};
                color: {theme.FG_MUTED};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.rgba(theme.INK_MID, 0.7)};
                color: {hover_color};
                border-color: {theme.rgba(hover_color, 0.5)};
            }}
        """)
        return btn

    def set_maximized(self, is_max: bool) -> None:
        self.max_btn.setText("❐" if is_max else "◻")
        self.max_btn.setToolTip("Restaurer" if is_max else "Agrandir")

    def show_update(self, version: str) -> None:
        self.update_btn.setText(f"▲ v{version} disponible")
        self.update_btn.show()

    def set_update_progress(self, label: str) -> None:
        self.update_btn.setText(label)
        self.update_btn.setEnabled(False)
        self.update_btn.show()

    def reset_update(self) -> None:
        self.update_btn.hide()
        self.update_btn.setEnabled(True)

    # ── Window dragging ──────────────────────────────────────────────────────
    # We delegate drag to the OS via QWindow.startSystemMove. That gets us
    # native edge-snap previews + Aero peek, instead of our own move() call
    # which the OS doesn't recognize as a drag.
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemMove():
                e.accept()
                return
            # Fallback: manual move (used if startSystemMove not supported)
            window = self.window()
            self._drag_offset = e.globalPosition() - QPointF(window.frameGeometry().topLeft())
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            new_pos = e.globalPosition() - self._drag_offset
            self.window().move(new_pos.toPoint())
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
            e.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Hero greeting
# ─────────────────────────────────────────────────────────────────────────────

class Hero(QWidget):
    _DAYS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
    _MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre")

    def __init__(self, name: str = "Romy", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        eyebrow = QLabel(self._format_eyebrow())
        eyebrow.setFont(theme.font("body", 11, QFont.Weight.DemiBold, letter_spacing=8))
        eyebrow.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        col.addWidget(eyebrow)

        # Line 1: "Bonjour, " + name (italic, turquoise) + "."
        line1 = QHBoxLayout()
        line1.setContentsMargins(0, 0, 0, 0)
        line1.setSpacing(0)

        greeting_text, _ = self._greeting()
        self._greet_lbl = QLabel(f"{greeting_text},  ")
        self._greet_lbl.setFont(theme.font("display", 30, QFont.Weight.Normal))
        self._greet_lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")

        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(theme.font("display", 30, QFont.Weight.Normal, italic=True))
        self._name_lbl.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")

        period_lbl = QLabel(".")
        period_lbl.setFont(theme.font("display", 30, QFont.Weight.Normal))
        period_lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")

        line1.addWidget(self._greet_lbl)
        line1.addWidget(self._name_lbl)
        line1.addWidget(period_lbl)
        line1.addStretch(1)
        col.addLayout(line1)

        # Line 2: question (italic, lighter weight)
        question_lbl = QLabel("Que veux-tu créer aujourd'hui ?")
        question_lbl.setFont(theme.font("display", 34, QFont.Weight.Light, italic=True))
        question_lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        col.addWidget(question_lbl)

        # Subtitle paragraph
        sub = QLabel(
            "Un atelier d'outils faits main, classés par envie. "
            "Chaque pièce a son atmosphère — pioche dans une catégorie "
            "ou reprends ce que tu faisais."
        )
        sub.setFont(theme.font("body", 14, QFont.Weight.Medium))
        sub.setStyleSheet(f"color: {theme.FG_MUTED}; background: transparent;")
        sub.setWordWrap(True)
        sub.setMaximumWidth(720)
        col.addWidget(sub)
        col.addSpacing(4)

    def _format_eyebrow(self) -> str:
        now = datetime.now()
        day = self._DAYS[now.weekday()]
        return f"{day} {now.day} {self._MONTHS[now.month - 1]} · {now:%H:%M}"

    def set_name(self, name: str) -> None:
        self._name_lbl.setText(name)

    @staticmethod
    def _greeting() -> tuple[str, str]:
        hour = datetime.now().hour
        if hour < 6:
            return "Bonne nuit", "Que veux-tu créer aujourd'hui ?"
        if hour < 12:
            return "Bonjour", "Que veux-tu créer aujourd'hui ?"
        if hour < 18:
            return "Bel après-midi", "Que veux-tu créer aujourd'hui ?"
        return "Belle soirée", "Que veux-tu créer aujourd'hui ?"


# ─────────────────────────────────────────────────────────────────────────────
# Section header (e.g. "I. Catégories" + "8 univers")
# ─────────────────────────────────────────────────────────────────────────────

class SectionHead(QWidget):
    def __init__(self, numeral: str, title: str, meta: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(12)

        num_lbl = QLabel(numeral)
        num_lbl.setFont(theme.font("display", 18, QFont.Weight.Light, italic=True))
        num_lbl.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        layout.addWidget(num_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(theme.font("display", 22, QFont.Weight.Medium))
        title_lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        layout.addWidget(title_lbl)

        layout.addStretch(1)

        self.meta_lbl = QLabel(meta)
        self.meta_lbl.setFont(theme.font("body", 11, QFont.Weight.DemiBold, letter_spacing=4))
        self.meta_lbl.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        layout.addWidget(self.meta_lbl)

    def set_meta(self, text: str) -> None:
        self.meta_lbl.setText(text)


# ─────────────────────────────────────────────────────────────────────────────
# Category tile — clickable, custom-painted (aura + frame + corners + arrow)
# ─────────────────────────────────────────────────────────────────────────────

class CategoryTile(QFrame):
    clicked = Signal(object)  # emits Category

    def __init__(self, cat: Category, count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cat = cat
        self.count = count
        self.setMinimumSize(200, 130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        # Hover state, driven by QPropertyAnimation on the `hoverProgress`
        # qProperty (0.0 idle → 1.0 fully hovered). paintEvent reads it to
        # intensify aura/border/corners and rotate the ↗ arrow.
        self._hover_progress: float = 0.0
        self._hover_anim = QPropertyAnimation(self, b"hoverProgress")
        self._hover_anim.setDuration(280)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Outer glow via QGraphicsDropShadowEffect — colored by the category
        # accent. blurRadius animates from 0 (idle) to 36 (hovered).
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(QColor(cat.c1))
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0.0)
        self.setGraphicsEffect(self._shadow)
        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius")
        self._shadow_anim.setDuration(280)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        # Top: icon glyph in a frosted square
        icon = QLabel(cat.icon)
        icon.setFixedSize(46, 46)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(theme.font("body", 24, QFont.Weight.Medium))
        icon.setStyleSheet(
            f"background-color: {theme.rgba(theme.PAPER, 0.10)};"
            f"border: 1px solid {theme.rgba(theme.PAPER, 0.22)};"
            f"border-radius: 14px;"
            f"color: {cat.c1};"
        )
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        # Bottom: name + count
        name = QLabel(cat.name)
        name.setFont(theme.font("display", 20, QFont.Weight.Medium))
        name.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        layout.addWidget(name)

        count_text = "AUCUN OUTIL" if count == 0 else (
            f"{count} OUTIL" if count == 1 else f"{count} OUTILS"
        )
        count_lbl = QLabel(count_text)
        count_lbl.setFont(theme.font("body", 10, QFont.Weight.DemiBold, letter_spacing=4))
        count_lbl.setStyleSheet(f"color: {theme.FG_MUTED}; background: transparent;")
        layout.addWidget(count_lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.cat)
        super().mousePressEvent(e)

    # ── Hover animation ──────────────────────────────────────────────────────
    def _get_hover_progress(self) -> float:
        return self._hover_progress

    def _set_hover_progress(self, value: float) -> None:
        self._hover_progress = float(value)
        self.update()

    hoverProgress = Property(float, _get_hover_progress, _set_hover_progress)

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_progress)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(self._shadow.blurRadius())
        self._shadow_anim.setEndValue(36.0 if target > 0 else 0.0)
        self._shadow_anim.start()

    # ── Painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(theme.RADIUS_TILE)
        h = self._hover_progress  # 0.0 idle → 1.0 hovered

        # Clip to rounded rect for the painted layers
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(clip)

        # Base colour
        p.fillRect(rect, QColor("#0a0d1f"))

        # Aura — radial gradient that grows + brightens with hover
        cx = rect.center().x()
        cy = rect.center().y()
        aura_radius = max(rect.width(), rect.height()) * (0.85 + 0.20 * h)
        grad = QRadialGradient(QPointF(cx, cy), aura_radius)
        c1 = QColor(self.cat.c1); c1.setAlpha(140 + int(80 * h))
        c2 = QColor(self.cat.c2); c2.setAlpha(110 + int(70 * h))
        end = QColor(self.cat.c2); end.setAlpha(0)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.4, c2)
        grad.setColorAt(0.85, end)
        p.fillRect(rect, grad)

        # Highlight wash (top-left bright, bottom-right shadow)
        wash = QRadialGradient(rect.left() + rect.width() * 0.3,
                               rect.top() + rect.height() * 0.2,
                               rect.width() * 0.6)
        wash.setColorAt(0.0, QColor(245, 241, 232, 36 + int(40 * h)))
        wash.setColorAt(0.7, QColor(0, 0, 0, 0))
        p.fillRect(rect, wash)

        p.restore()

        # Inner frame (10px inset) — subtle, slightly brighter on hover
        inner = rect.adjusted(10, 10, -10, -10)
        pen = QPen(QColor(245, 241, 232, 46 + int(50 * h)), 1.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(inner, 14, 14)

        # Gold L-corners — opacity grows with hover
        gold = QColor(theme.GOLD)
        gold.setAlpha(int(160 + 95 * h))
        p.setPen(QPen(gold, 1.0))
        L = 14
        tl = inner.topLeft()
        p.drawLine(QPointF(tl.x(), tl.y() + L), QPointF(tl.x(), tl.y()))
        p.drawLine(QPointF(tl.x(), tl.y()), QPointF(tl.x() + L, tl.y()))
        br = inner.bottomRight()
        p.drawLine(QPointF(br.x(), br.y() - L), QPointF(br.x(), br.y()))
        p.drawLine(QPointF(br.x(), br.y()), QPointF(br.x() - L, br.y()))

        # Outer border — turquoise tint, brighter + thicker on hover
        border_alpha = 38 + int(140 * h)
        border_pen = QPen(QColor(95, 200, 216, border_alpha), 1.0 + 0.5 * h)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        # Top-right arrow badge — circle stays, ↗ glyph rotates -45°
        a_size = 28.0
        a_rect = QRectF(rect.right() - 18 - a_size, rect.top() + 18, a_size, a_size)
        p.setPen(QPen(QColor(245, 241, 232, 64 + int(60 * h)), 1.0))
        p.setBrush(QBrush(QColor(245, 241, 232, 30 + int(60 * h))))
        p.drawEllipse(a_rect)

        p.save()
        a_center = a_rect.center()
        p.translate(a_center)
        p.rotate(-45.0 * h)
        p.translate(-a_center)
        p.setPen(QPen(QColor(theme.FG), 1.0))
        p.setFont(theme.font("body", 14, QFont.Weight.Bold))
        p.drawText(a_rect, Qt.AlignmentFlag.AlignCenter, "↗")
        p.restore()

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Recent tile (5-col strip)
# ─────────────────────────────────────────────────────────────────────────────

class RecentTile(QFrame):
    clicked = Signal(object)  # emits ToolCard

    def __init__(self, tool: ToolCard, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tool = tool
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        icon = QLabel(tool.icon)
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(theme.font("body", 18, QFont.Weight.Normal))
        icon.setStyleSheet(
            f"background-color: {theme.INK_DEEPEST};"
            f"border: 1px solid {theme.rgba(theme.TURQUOISE, 0.25)};"
            f"border-radius: 11px;"
            f"color: {tool.accent};"
        )
        layout.addWidget(icon)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)
        name = QLabel(tool.name)
        name.setFont(theme.font("body", 13, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        info_col.addWidget(name)
        when = QLabel((tool.last_used or "JAMAIS OUVERT").upper())
        when.setFont(theme.font("body", 10, QFont.Weight.Medium, letter_spacing=4))
        when.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        info_col.addWidget(when)
        layout.addLayout(info_col)
        layout.addStretch(1)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tool)
        super().mousePressEvent(e)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(theme.RADIUS_CARD)

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(clip)
        p.fillRect(rect, QColor(35, 42, 90, int(0.5 * 255)))

        # Diagonal accent wash
        wash = QRadialGradient(rect.topLeft(), rect.width() * 1.2)
        accent = QColor(self.tool.accent); accent.setAlpha(40)
        wash.setColorAt(0.0, accent)
        end = QColor(self.tool.accent); end.setAlpha(0)
        wash.setColorAt(0.7, end)
        p.fillRect(rect, wash)
        p.restore()

        p.setPen(QPen(QColor(95, 200, 216, 38), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Empty placeholder for the recents strip
# ─────────────────────────────────────────────────────────────────────────────

class EmptyTile(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(theme.RADIUS_CARD)

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(clip)
        p.fillRect(rect, QColor(20, 24, 50, int(0.4 * 255)))
        p.restore()

        # Dashed dim border
        pen = QPen(QColor(112, 128, 168, 90), 1.0, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        # Centered grey ✕
        p.setPen(QColor(112, 128, 168, 120))
        p.setFont(theme.font("body", 18, QFont.Weight.Light))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "✕")
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Placeholder modal shown when a tool is clicked (until step 5/6 ports BaseTool)
# ─────────────────────────────────────────────────────────────────────────────

class CategoryBrowserDialog(QDialog):
    """Modal that lists the tools in a category (or shows 'À venir' when empty).

    Emits `tool_clicked(ToolCard)` when the user picks a tool from the list,
    then closes itself with `accept()`.
    """

    tool_clicked = Signal(object)

    def __init__(self, cat: Category, tools: list[ToolCard],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        # Size adapts to content: ~84px per tool, max 6 visible
        body_h = 60 if not tools else min(6, len(tools)) * 84 + 12
        total_h = 110 + body_h + 24
        self.setFixedSize(560, total_h)

        outer = QFrame(self)
        outer.setObjectName("CategoryCard")
        outer.setGeometry(0, 0, 560, total_h)
        outer.setStyleSheet(f"""
            #CategoryCard {{
                background-color: {theme.INK_DEEP};
                border: 1px solid {theme.rgba(cat.c1, 0.55)};
                border-radius: 22px;
            }}
        """)

        col = QVBoxLayout(outer)
        col.setContentsMargins(28, 22, 28, 22)
        col.setSpacing(14)

        # Header
        head = QHBoxLayout()
        head.setSpacing(14)

        icon = QLabel(cat.icon)
        icon.setFixedSize(46, 46)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(theme.font("body", 24, QFont.Weight.Medium))
        icon.setStyleSheet(
            f"background-color: {theme.rgba(cat.c1, 0.15)};"
            f"border: 1px solid {theme.rgba(cat.c1, 0.35)};"
            f"border-radius: 14px;"
            f"color: {cat.c1};"
        )
        head.addWidget(icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 0, 0, 0)
        title = QLabel(cat.name)
        title.setFont(theme.font("display", 22, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        title_col.addWidget(title)
        meta = QLabel(
            "Aucun outil pour le moment" if not tools else
            f"{len(tools)} outil{'s' if len(tools) > 1 else ''} dans cette catégorie"
        )
        meta.setFont(theme.font("body", 11, QFont.Weight.DemiBold, letter_spacing=4))
        meta.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        title_col.addWidget(meta)
        head.addLayout(title_col)

        head.addStretch(1)

        close = QPushButton("✕")
        close.setFixedSize(34, 34)
        close.setStyleSheet(theme.qss_close_btn())
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        head.addWidget(close)

        col.addLayout(head)

        # Body — tool list, or empty-state placeholder
        if tools:
            for t in tools:
                tile = RecentTile(t)
                tile.clicked.connect(self._handle_tool_pick)
                col.addWidget(tile)
        else:
            empty = QLabel("Cette catégorie attend ses créations.\n"
                           "Reviens bientôt — d'autres outils arrivent.")
            empty.setFont(theme.font("body", 13, italic=True))
            empty.setStyleSheet(
                f"color: {theme.FG_MUTED}; background: transparent;"
                f"padding: 20px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            col.addWidget(empty)

        col.addStretch(1)

    def _handle_tool_pick(self, tool: ToolCard) -> None:
        self.tool_clicked.emit(tool)
        self.accept()


class ToolPlaceholderDialog(QDialog):
    def __init__(self, tool: ToolCard, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(440, 240)

        outer = QFrame(self)
        outer.setObjectName("PlaceholderCard")
        outer.setGeometry(0, 0, 440, 240)
        outer.setStyleSheet(f"""
            #PlaceholderCard {{
                background-color: {theme.INK_DEEP};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.4)};
                border-radius: 22px;
            }}
        """)

        col = QVBoxLayout(outer)
        col.setContentsMargins(28, 24, 28, 24)
        col.setSpacing(12)

        head = QHBoxLayout()
        icon = QLabel(tool.icon)
        icon.setFont(theme.font("body", 28))
        icon.setStyleSheet(f"color: {tool.accent}; background: transparent;")
        head.addWidget(icon)
        title = QLabel(tool.name)
        title.setFont(theme.font("display", 22, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        head.addWidget(title)
        head.addStretch(1)
        col.addLayout(head)

        msg = QLabel(
            "Cet outil sera disponible une fois la migration\n"
            "vers la nouvelle interface terminée (étape 5/6)."
        )
        msg.setFont(theme.font("body", 13))
        msg.setStyleSheet(f"color: {theme.FG_MUTED}; background: transparent;")
        msg.setWordWrap(True)
        col.addWidget(msg)

        col.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok = QPushButton("D'accord")
        ok.setStyleSheet(theme.qss_button_primary())
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        col.addLayout(btn_row)


# ─────────────────────────────────────────────────────────────────────────────
# Name dialog — first-launch greeting + later edits via the settings button
# ─────────────────────────────────────────────────────────────────────────────

class NameDialog(QDialog):
    """Asks the user for the name displayed in the hub greeting.

    Use `value()` after `exec()` to get the trimmed name, or empty string
    if the user cancelled / left the field blank.
    """

    MAX_LEN = 24

    def __init__(self, current: str = "", parent: QWidget | None = None,
                 first_launch: bool = False) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(480, 300)

        self._value = ""

        outer = QFrame(self)
        outer.setObjectName("NameCard")
        outer.setGeometry(0, 0, 480, 300)
        outer.setStyleSheet(f"""
            #NameCard {{
                background-color: {theme.INK_DEEP};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.5)};
                border-radius: 22px;
            }}
        """)

        col = QVBoxLayout(outer)
        col.setContentsMargins(32, 26, 32, 24)
        col.setSpacing(14)

        eyebrow = QLabel("BIENVENUE" if first_launch else "TON PRÉNOM")
        eyebrow.setFont(theme.font("body", 11, QFont.Weight.DemiBold, letter_spacing=8))
        eyebrow.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        col.addWidget(eyebrow)

        title = QLabel("Comment dois-je t'appeler ?"
                       if first_launch else "Modifier ton prénom")
        title.setFont(theme.font("display", 26, QFont.Weight.Normal, italic=True))
        title.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        col.addWidget(title)

        if first_launch:
            sub = QLabel(
                "Ton prénom apparaîtra dans le mot de bienvenue à chaque "
                "ouverture du hub. Tu pourras le changer plus tard."
            )
            sub.setFont(theme.font("body", 12))
            sub.setStyleSheet(f"color: {theme.FG_MUTED}; background: transparent;")
            sub.setWordWrap(True)
            col.addWidget(sub)

        self._input = QLineEdit()
        self._input.setText(current)
        self._input.setMaxLength(self.MAX_LEN)
        self._input.setPlaceholderText("Romy")
        self._input.setStyleSheet(theme.qss_input())
        self._input.returnPressed.connect(self._accept_value)
        col.addWidget(self._input)

        col.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if not first_launch:
            cancel = QPushButton("Annuler")
            cancel.setStyleSheet(theme.qss_button_ghost())
            cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel.clicked.connect(self.reject)
            btn_row.addWidget(cancel)

        btn_row.addStretch(1)

        ok = QPushButton("Valider" if not first_launch else "C'est parti")
        ok.setStyleSheet(theme.qss_button_primary())
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self._accept_value)
        ok.setDefault(True)
        btn_row.addWidget(ok)

        col.addLayout(btn_row)

        # Focus the input so user can start typing immediately.
        self._input.setFocus()
        self._input.selectAll()

    def _accept_value(self) -> None:
        self._value = self._input.text().strip()
        if self._value:
            self.accept()
        else:
            # Empty input — just shake the field briefly via a stylesheet flash
            self._input.setStyleSheet(theme.qss_input().replace(
                theme.rgba(theme.TURQUOISE, 0.30),
                theme.rgba(theme.ERROR, 0.6),
            ))
            self._input.setFocus()

    def value(self) -> str:
        return self._value

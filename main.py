"""MyHub53 — entry point (PySide6).

Frameless main window hosting the hub. Tools open via the registry; for the
duration of the migration, clicking a tool shows a placeholder dialog.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QCursor
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from core import theme
from core.atmos import AtmosBg
from core.effects import ParticleLayer
from core.hub_widgets import (
    CategoryBrowserDialog,
    CategoryTile,
    EmptyTile,
    HeaderBar,
    Hero,
    NameDialog,
    RecentTile,
    SectionHead,
    SettingsDialog,
    ToolPlaceholderDialog,
)
import core.settings as settings_store
from core.win_chrome import enable_native_features, is_nccalcsize
from core.updater import (
    check_update,
    download_and_update,
    has_update,
    load_local_version,
)
from tools.registry import (
    CATEGORIES,
    TOOLS,
    Category,
    ToolCard,
    category_count,
    tools_in_category,
)

GITHUB_REPO = "LucasOnCode/MyHub53"
VERSION_FILE = Path(__file__).parent / "version.txt"

HUB_SETTINGS_ID = "hub"
DEFAULT_USER_NAME = "Romy"

RECENT_COLS = 5
WINDOW_W = 1280
WINDOW_H = 900

# Minimum window size — flexible enough to allow narrow 2-column layouts.
MIN_W = 700
MIN_H = 600

# Width of the invisible ring around the window used to detect edge resizing.
EDGE_MARGIN = 6

# Responsive thresholds for the category grid (in viewport width px).
CAT_COLS_MAX = 4
CAT_COLS_MIN = 2
CAT_TILE_MIN_W = 200       # must match CategoryTile.setMinimumSize width
CAT_BREAK_3 = 920          # below this → 3 cols
CAT_BREAK_2 = 660          # below this → 2 cols


def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


class SmoothScrollArea(QScrollArea):
    """Forces a full viewport repaint on scroll.

    The default QScrollArea blits viewport pixels for performance. With
    semi-transparent children layered over a non-scrolling background
    (AtmosBg behind the viewport), the blit creates ghost trails. Calling
    update() after each scroll forces a full repaint and eliminates the
    artefact.
    """

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.viewport().update()


class MainWindow(QWidget):
    update_check_done = Signal(object, object)        # (version, url) | (None, None)
    download_progress = Signal(int)
    download_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.local_version = load_local_version(VERSION_FILE)
        self._remote_version: Optional[str] = None
        self._download_url: Optional[str] = None
        self._filter_cat: Optional[str] = None
        self._native_chrome_done = False

        # Load saved hub-level settings (user name, future preferences).
        hub_cfg = settings_store.load(HUB_SETTINGS_ID)
        self._user_name = hub_cfg.get("user_name", DEFAULT_USER_NAME)
        self._name_was_set = bool(hub_cfg.get("user_name"))
        self._particles_enabled: bool = bool(hub_cfg.get("particles_enabled", True))

        # Reasons currently keeping the particle layer paused. Empty set =
        # animations run; any reason in the set = paused. Centralising the
        # state here means a single rule (`particles run iff no reasons`).
        self._pause_reasons: set[str] = set()
        if not self._particles_enabled:
            self._pause_reasons.add("user_off")
        self._open_tools: list = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowTitle("MyHub53")
        self.setMinimumSize(MIN_W, MIN_H)
        self.setMouseTracking(True)
        self._resize_edges: Qt.Edges = Qt.Edge(0)

        # Pick an initial size that fits the user's screen comfortably.
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            init_w = min(WINDOW_W, max(MIN_W, avail.width() - 80))
            init_h = min(WINDOW_H, max(MIN_H, avail.height() - 80))
        else:
            init_w, init_h = WINDOW_W, WINDOW_H
        self.resize(init_w, init_h)

        try:
            self.setWindowIcon(QIcon(resource_path("icone.ico")))
        except Exception:
            pass

        # ── Layered children: AtmosBg → ParticleLayer → content ──────────
        # AtmosBg + ParticleLayer have WA_TransparentForMouseEvents so events
        # pass through them; in the EDGE_MARGIN ring (where content doesn't
        # cover) they fall through to MainWindow's own mouse handlers.
        self.atmos = AtmosBg(self)
        self.atmos.setGeometry(0, 0, self.width(), self.height())

        self.particles = ParticleLayer(self, density=28, fps=60)
        self.particles.setGeometry(0, 0, self.width(), self.height())

        self.content = QWidget(self)
        self.content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.content.setGeometry(EDGE_MARGIN, EDGE_MARGIN,
                                  self.width() - 2 * EDGE_MARGIN,
                                  self.height() - 2 * EDGE_MARGIN)
        self.content.raise_()

        outer = QVBoxLayout(self.content)
        outer.setContentsMargins(28, 16, 28, 20)
        outer.setSpacing(14)

        # Header (always visible, never scrolls)
        self.header = HeaderBar(self.local_version)
        self.header.close_clicked.connect(self.close)
        self.header.minimize_clicked.connect(self.showMinimized)
        self.header.maximize_clicked.connect(self._toggle_maximize)
        self.header.settings_clicked.connect(self._on_settings)
        self.header.update_clicked.connect(self._on_update_clicked)
        outer.addWidget(self.header)

        # Body — scrolls when window is too small to show everything
        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground)

        body = QWidget()
        body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)

        # Hero
        self.hero = Hero(self._user_name)
        col.addWidget(self.hero)

        # Categories section
        self.cat_section = SectionHead(
            numeral="I.", title="Catégories",
            meta=f"{len(CATEGORIES)} UNIVERS"
        )
        col.addWidget(self.cat_section)

        # Build all category tiles up front; the grid layout is rebuilt on
        # resize to switch column counts (4 ↔ 3 ↔ 2) responsively.
        self.cat_tiles: list[CategoryTile] = []
        for cat in CATEGORIES:
            tile = CategoryTile(cat, category_count(cat))
            tile.clicked.connect(self._on_cat_clicked)
            self.cat_tiles.append(tile)

        cat_grid_holder = QWidget()
        cat_grid_holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cat_grid_holder.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Expanding)
        self.cat_grid = QGridLayout(cat_grid_holder)
        self.cat_grid.setContentsMargins(0, 0, 0, 0)
        self.cat_grid.setHorizontalSpacing(theme.GAP_GRID)
        self.cat_grid.setVerticalSpacing(theme.GAP_GRID)
        self._current_cat_cols = 0
        col.addWidget(cat_grid_holder, stretch=1)
        self._rebuild_cat_grid(CAT_COLS_MAX)  # initial population

        # Recents section
        self.rec_section = SectionHead(
            numeral="II.", title="Récemment ouverts",
            meta="REPRENDRE OÙ TU EN ÉTAIS"
        )
        col.addWidget(self.rec_section)

        rec_grid_holder = QWidget()
        rec_grid_holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.rec_grid = QGridLayout(rec_grid_holder)
        self.rec_grid.setContentsMargins(0, 0, 0, 0)
        self.rec_grid.setHorizontalSpacing(14)
        for c in range(RECENT_COLS):
            self.rec_grid.setColumnStretch(c, 1)
        col.addWidget(rec_grid_holder)
        self._rebuild_recents()

        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, stretch=1)

        # Centre on screen
        self._centre_on_screen()

        # ── Update wiring ─────────────────────────────────────────────────
        self.update_check_done.connect(self._on_check_done)
        self.download_progress.connect(self._on_download_progress)
        self.download_failed.connect(self._on_download_failed)

        QTimer.singleShot(3000, lambda: self._check_for_updates(silent=True))

    # ── Layered geometry ─────────────────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "atmos"):
            self.atmos.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "particles"):
            self.particles.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "content"):
            margin = 0 if self.isMaximized() else EDGE_MARGIN
            self.content.setGeometry(margin, margin,
                                      self.width() - 2 * margin,
                                      self.height() - 2 * margin)
        if hasattr(self, "cat_tiles"):
            self._update_responsive_layout()

    # ── Responsive category grid ─────────────────────────────────────────────
    def _desired_cat_cols(self) -> int:
        """Pick column count based on the viewport's available width."""
        if not hasattr(self, "scroll"):
            return CAT_COLS_MAX
        avail = self.scroll.viewport().width()
        if avail <= 0:
            return CAT_COLS_MAX
        if avail < CAT_BREAK_2:
            return 2
        if avail < CAT_BREAK_3:
            return 3
        return CAT_COLS_MAX

    def _update_responsive_layout(self) -> None:
        cols = self._desired_cat_cols()
        if cols == self._current_cat_cols:
            return
        self._rebuild_cat_grid(cols)

    def _rebuild_cat_grid(self, cols: int) -> None:
        # Detach all tiles
        while self.cat_grid.count():
            self.cat_grid.takeAt(0)
        # Reset stretches (clear leftovers from a previous column count)
        for c in range(CAT_COLS_MAX):
            self.cat_grid.setColumnStretch(c, 0)
        max_possible_rows = (len(self.cat_tiles) + CAT_COLS_MIN - 1) // CAT_COLS_MIN
        for r in range(max_possible_rows):
            self.cat_grid.setRowStretch(r, 0)
        # Apply new layout
        for c in range(cols):
            self.cat_grid.setColumnStretch(c, 1)
        n_rows = (len(self.cat_tiles) + cols - 1) // cols
        for r in range(n_rows):
            self.cat_grid.setRowStretch(r, 1)
        for idx, tile in enumerate(self.cat_tiles):
            r, c = divmod(idx, cols)
            self.cat_grid.addWidget(tile, r, c)
        self._current_cat_cols = cols

    # ── Frameless edge-resize ────────────────────────────────────────────────
    def _edge_at(self, pos: QPoint) -> Qt.Edges:
        edges = Qt.Edge(0)
        if self.isMaximized():
            return edges
        m = EDGE_MARGIN
        x, y = pos.x(), pos.y()
        if x <= m:
            edges |= Qt.Edge.LeftEdge
        if x >= self.width() - m:
            edges |= Qt.Edge.RightEdge
        if y <= m:
            edges |= Qt.Edge.TopEdge
        if y >= self.height() - m:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges: Qt.Edges) -> Qt.CursorShape:
        L, R, T, B = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        if edges == (T | L) or edges == (B | R):
            return Qt.CursorShape.SizeFDiagCursor
        if edges == (T | R) or edges == (B | L):
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (L | R):
            return Qt.CursorShape.SizeHorCursor
        if edges & (T | B):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mouseMoveEvent(self, event):
        edges = self._edge_at(event.position().toPoint())
        if edges:
            self.setCursor(self._cursor_for_edges(edges))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._edge_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    event.accept()
                    return
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    # ── Native Win32 chrome (Aero Snap, Win+arrow shortcuts) ─────────────────
    def showEvent(self, event):
        super().showEvent(event)
        # Resume animations whenever the window comes back from hidden state.
        self._remove_pause_reason("hidden")
        if not self._native_chrome_done:
            enable_native_features(self)
            self._native_chrome_done = True
            # Ask for the user's name on first launch — once the window has
            # had time to paint so the dialog appears centered cleanly.
            if not self._name_was_set:
                QTimer.singleShot(350, lambda: self._ask_user_name(first_launch=True))

    def nativeEvent(self, eventType, message):
        # When Aero Snap styles are added, Windows wants to draw a thin
        # non-client frame. Eat WM_NCCALCSIZE to keep the window visually
        # frameless.
        if is_nccalcsize(eventType, message):
            return True, 0
        return super().nativeEvent(eventType, message)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, "header"):
                self.header.set_maximized(self.isMaximized())
            # Pause animations while minimised — they're invisible anyway.
            if self.isMinimized():
                self._add_pause_reason("minimized")
            else:
                self._remove_pause_reason("minimized")

    def hideEvent(self, event):
        super().hideEvent(event)
        self._add_pause_reason("hidden")

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _centre_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    # ── Recents grid ─────────────────────────────────────────────────────────
    def _rebuild_recents(self) -> None:
        # Clear children
        while self.rec_grid.count():
            item = self.rec_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        visible = tools_in_category(self._filter_cat)[:RECENT_COLS]
        for c in range(RECENT_COLS):
            if c < len(visible):
                tile = RecentTile(visible[c])
                tile.clicked.connect(self._on_tool_clicked)
                self.rec_grid.addWidget(tile, 0, c)
            else:
                self.rec_grid.addWidget(EmptyTile(), 0, c)

    # ── User actions ─────────────────────────────────────────────────────────
    def _on_cat_clicked(self, cat: Category) -> None:
        tools = list(TOOLS) if cat.is_all else tools_in_category(cat.id)
        dlg = CategoryBrowserDialog(cat, tools, self)
        dlg.tool_clicked.connect(self._on_tool_clicked)
        dlg.exec()

    def _on_tool_clicked(self, tool: ToolCard) -> None:
        try:
            window = tool.klass(self)
            window.show()
            self._open_tools.append(window)
            self._add_pause_reason("tool_open")
            window.destroyed.connect(self._on_tool_destroyed)
        except Exception as exc:
            dlg = ToolPlaceholderDialog(tool, self)
            dlg.exec()
            print(f"[hub] failed to open {tool.id}: {exc}")

    def _on_tool_destroyed(self, obj=None) -> None:
        # `obj` is the QObject being destroyed. Filter out dead references.
        self._open_tools = [w for w in self._open_tools
                            if w is not None and w is not obj]
        if not self._open_tools:
            self._remove_pause_reason("tool_open")

    # ── Animation pause/resume ───────────────────────────────────────────────
    def _add_pause_reason(self, reason: str) -> None:
        self._pause_reasons.add(reason)
        self._sync_animations()

    def _remove_pause_reason(self, reason: str) -> None:
        self._pause_reasons.discard(reason)
        self._sync_animations()

    def _sync_animations(self) -> None:
        running = not self._pause_reasons
        if hasattr(self, "particles"):
            self.particles.set_running(running)

    def _on_settings(self) -> None:
        dlg = SettingsDialog(
            current={
                "user_name": self._user_name if self._name_was_set else "",
                "particles_enabled": self._particles_enabled,
            },
            parent=self,
        )
        if dlg.exec() != SettingsDialog.DialogCode.Accepted:
            return
        new = dlg.values()
        # Apply name change
        new_name = new.get("user_name", "").strip()
        if new_name and new_name != self._user_name:
            self._user_name = new_name
            self._name_was_set = True
            self.hero.set_name(new_name)
        # Apply particles toggle
        new_particles = bool(new.get("particles_enabled", True))
        if new_particles != self._particles_enabled:
            self._particles_enabled = new_particles
            if new_particles:
                self._remove_pause_reason("user_off")
            else:
                self._add_pause_reason("user_off")
        # Persist everything in one shot
        settings_store.save(HUB_SETTINGS_ID, {
            "user_name": self._user_name,
            "particles_enabled": self._particles_enabled,
        })

    def _ask_user_name(self, first_launch: bool) -> None:
        dlg = NameDialog(self._user_name if self._name_was_set else "",
                         self, first_launch=first_launch)
        result = dlg.exec()
        if result == NameDialog.DialogCode.Accepted:
            name = dlg.value()
            if name:
                self._user_name = name
                self._name_was_set = True
                settings_store.save(HUB_SETTINGS_ID, {"user_name": name})
                self.hero.set_name(name)
        elif first_launch:
            # User dismissed first-launch dialog — fall back to default and
            # remember so we don't re-prompt every startup.
            settings_store.save(HUB_SETTINGS_ID, {"user_name": self._user_name})
            self._name_was_set = True

    # ── Updates ──────────────────────────────────────────────────────────────
    def _check_for_updates(self, silent: bool = True) -> None:
        def run():
            v, u = check_update(GITHUB_REPO)
            self.update_check_done.emit(v, u)
        threading.Thread(target=run, daemon=True).start()

    def _on_check_done(self, version: Optional[str], url: Optional[str]) -> None:
        if not version:
            return
        self._remote_version = version
        self._download_url = url
        if has_update(self.local_version, version):
            self.header.show_update(version)

    def _on_update_clicked(self) -> None:
        if not self._download_url:
            return
        self.header.set_update_progress("Téléchargement…")

        def run():
            try:
                download_and_update(
                    self._download_url,
                    lambda p: self.download_progress.emit(int(p)),
                )
            except RuntimeError as e:
                self.download_failed.emit(str(e))

        threading.Thread(target=run, daemon=True).start()

    def _on_download_progress(self, pct: int) -> None:
        self.header.set_update_progress(f"Téléchargement {pct}%")

    def _on_download_failed(self, msg: str) -> None:
        self.header.reset_update()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MyHub53")
    theme.load_fonts()
    app.setFont(theme.font("body", 13))
    app.setStyleSheet(theme.qss_app())

    try:
        app.setWindowIcon(QIcon(resource_path("icone.ico")))
    except Exception:
        pass

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

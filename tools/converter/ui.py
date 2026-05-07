"""MyFileConverter — YouTube → MP3/FLAC/M4A/WAV/OGG.

Aquatic-univers PySide6 UI. The yt-dlp logic is identical to the original
tkinter version; only the presentation layer changed. Worker threads emit
Qt signals to push updates to the UI thread safely.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import yt_dlp

import core.settings as settings_store
from core import theme
from core.base_tool import BaseTool

TOOL_ID = "converter"

FORMAT_CODEC       = {"MP3": "mp3", "FLAC": "flac", "M4A": "m4a", "WAV": "wav", "OGG": "vorbis"}
SUPPORTS_THUMBNAIL = {"MP3", "M4A"}


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (unchanged from the tkinter version)
# ─────────────────────────────────────────────────────────────────────────────

def _resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    root = Path(__file__).resolve().parent.parent.parent
    return str(root / rel)


def _validate_url(url: str) -> bool:
    if not url:
        return False
    try:
        p = urllib.parse.urlparse(url if url.startswith("http") else "https://" + url)
        return bool(p.netloc)
    except Exception:
        return False


def _check_destination(path: str) -> tuple[bool, str]:
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Impossible de créer le dossier : {e}"
    if not os.access(str(p), os.W_OK):
        return False, "Dossier non accessible en écriture"
    return True, ""


def _format_duration(sec) -> str:
    if not sec:
        return "--:--"
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def _format_speed(bps) -> str:
    if not bps:
        return ""
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} MB/s"
    return f"{bps / 1_000:.0f} KB/s"


def _load_history() -> list:
    hf = settings_store.history_file(TOOL_ID)
    if hf.exists():
        try:
            with open(hf, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _append_history(title: str, url: str, folder: str, fmt: str) -> None:
    hf = settings_store.history_file(TOOL_ID)
    h = _load_history()
    h.insert(0, {"title": title, "url": url, "folder": folder,
                 "format": fmt, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(hf, "w", encoding="utf-8") as f:
        json.dump(h[:200], f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Track row widget
# ─────────────────────────────────────────────────────────────────────────────

class _TrackRow(QFrame):
    """A single track in the converter's track list."""

    def __init__(self, idx: int, title: str, duration_sec, is_dup: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.idx = idx
        self.is_dup = is_dup
        self.setObjectName("TrackRow")
        self.setStyleSheet(f"""
            #TrackRow {{
                background-color: {theme.rgba(theme.INK_DEEP, 0.45)};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.10)};
                border-radius: 10px;
            }}
            #TrackRow:hover {{
                border-color: {theme.rgba(theme.TURQUOISE, 0.30)};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(not is_dup)
        self.checkbox.setStyleSheet(f"""
            QCheckBox {{ color: transparent; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                background: {theme.rgba(theme.INK_DEEPEST, 0.6)};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.5)};
                border-radius: 4px;
            }}
            QCheckBox::indicator:checked {{
                background: {theme.TURQUOISE};
                border-color: {theme.TURQUOISE};
            }}
        """)
        layout.addWidget(self.checkbox)

        idx_lbl = QLabel(f"{idx + 1:02d}")
        idx_lbl.setFont(theme.font("mono", 11, QFont.Weight.Medium))
        idx_lbl.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        idx_lbl.setFixedWidth(26)
        layout.addWidget(idx_lbl)

        title_text = title if len(title) <= 60 else title[:60] + "…"
        if is_dup:
            title_text += "   · déjà téléchargé"
        title_lbl = QLabel(title_text)
        title_lbl.setFont(theme.font("body", 13))
        title_lbl.setStyleSheet(
            f"color: {theme.FG_DIM if is_dup else theme.FG};"
            f"background: transparent;"
        )
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(title_lbl, stretch=1)

        self.speed_lbl = QLabel("")
        self.speed_lbl.setFont(theme.font("mono", 10, QFont.Weight.Medium))
        self.speed_lbl.setStyleSheet(f"color: {theme.GOLD}; background: transparent;")
        self.speed_lbl.setFixedWidth(72)
        self.speed_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.speed_lbl)

        dur_lbl = QLabel(_format_duration(duration_sec))
        dur_lbl.setFont(theme.font("mono", 11))
        dur_lbl.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        dur_lbl.setFixedWidth(46)
        dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(dur_lbl)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(80)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {theme.rgba(theme.INK_DEEPEST, 0.6)};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.TURQUOISE}, stop:1 {theme.IRIS});
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, v: bool) -> None:
        self.checkbox.setChecked(v)

    def set_progress(self, pct: int) -> None:
        self.progress.setValue(max(0, min(100, int(pct))))

    def set_speed(self, text: str) -> None:
        self.speed_lbl.setText(text)


# ─────────────────────────────────────────────────────────────────────────────
# Pill button group helper (format / quality / workers)
# ─────────────────────────────────────────────────────────────────────────────

class _PillGroup(QWidget):
    """A horizontal row of mutually exclusive pill buttons."""

    changed = Signal(str)

    def __init__(self, label: str, values: list[str], default: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        lbl = QLabel(label.upper())
        lbl.setFont(theme.font("body", 10, QFont.Weight.DemiBold, letter_spacing=4))
        lbl.setStyleSheet(f"color: {theme.FG_DIM}; background: transparent;")
        outer.addWidget(lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for v in values:
            btn = QPushButton(v)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            active = (v == default)
            btn.setChecked(active)
            btn.setStyleSheet(theme.qss_pill(active=active))
            self._group.addButton(btn)
            self._buttons[v] = btn
            row.addWidget(btn)
        row.addStretch(1)
        outer.addLayout(row)

        self._group.buttonClicked.connect(self._on_clicked)

    def _on_clicked(self, _btn) -> None:
        for v, b in self._buttons.items():
            b.setStyleSheet(theme.qss_pill(active=b.isChecked()))
        self.changed.emit(self.value())

    def value(self) -> str:
        for v, b in self._buttons.items():
            if b.isChecked():
                return v
        return ""

    def set_enabled(self, enabled: bool) -> None:
        for b in self._buttons.values():
            b.setEnabled(enabled)
        self.setEnabled(enabled)


# ─────────────────────────────────────────────────────────────────────────────
# Converter tool
# ─────────────────────────────────────────────────────────────────────────────

class ConverterTool(BaseTool):
    # Worker → UI signals
    preview_ready    = Signal(list)             # list of track dicts
    preview_failed   = Signal(str)
    row_progress     = Signal(int, int)         # (idx, pct)
    row_speed        = Signal(int, str)         # (idx, speed text)
    counter_changed  = Signal(int, int)         # (done, total)
    download_done    = Signal(int, list)        # (done, errors)
    download_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        self._cfg = settings_store.load(TOOL_ID)
        self._tracks: list[dict] = []
        self._track_rows: list[_TrackRow] = []
        self._cancel_flag = threading.Event()
        self._last_clipboard = ""
        super().__init__(
            parent,
            name="MyFileConverter",
            accent=theme.TURQUOISE,
            univers="aquatic",
            width=820, height=740,
            min_w=700, min_h=580,
        )

    # ── Build UI ─────────────────────────────────────────────────────────────
    def build(self) -> None:
        self._build_url_section()
        self._build_options_section()
        self._build_tracks_section()
        self._build_destination_section()
        self._build_actions_section()
        self._make_status_bar("Colle une URL et clique sur Analyser.")
        self._wire_signals()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setFont(theme.font("body", 10, QFont.Weight.DemiBold, letter_spacing=4))
        lbl.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        return lbl

    def _build_url_section(self) -> None:
        self.body_layout.addWidget(self._section_label("URL"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Colle ici une URL YouTube…")
        self._url_input.setStyleSheet(theme.qss_input())
        self._url_input.returnPressed.connect(self._fetch_preview)
        row.addWidget(self._url_input, stretch=1)

        self._analyze_btn = QPushButton("Analyser  ↗")
        self._analyze_btn.setStyleSheet(theme.qss_button_primary())
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.clicked.connect(self._fetch_preview)
        row.addWidget(self._analyze_btn)

        self.body_layout.addLayout(row)

    def _build_options_section(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(28)

        self._fmt_pill = _PillGroup("Format",
                                     ["MP3", "FLAC", "M4A", "WAV", "OGG"],
                                     self._cfg.get("format", "MP3"))
        self._fmt_pill.changed.connect(self._on_format_change)
        row.addWidget(self._fmt_pill)

        self._qual_pill = _PillGroup("Qualité (MP3)",
                                      ["128", "192", "320"],
                                      self._cfg.get("quality", "192"))
        row.addWidget(self._qual_pill)

        self._workers_pill = _PillGroup("En parallèle",
                                         ["1", "2", "3", "4", "5"],
                                         str(self._cfg.get("workers", 2)))
        row.addWidget(self._workers_pill)

        row.addStretch(1)

        history_btn = QPushButton("Historique")
        history_btn.setStyleSheet(theme.qss_button_ghost())
        history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        history_btn.clicked.connect(self._show_history)
        row.addWidget(history_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self.body_layout.addLayout(row)
        self._on_format_change(self._fmt_pill.value())

    def _on_format_change(self, fmt: str) -> None:
        self._qual_pill.set_enabled(fmt == "MP3")

    def _build_tracks_section(self) -> None:
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self._section_label("Morceaux"))
        self._count_lbl = QLabel("")
        self._count_lbl.setFont(theme.font("mono", 11, QFont.Weight.DemiBold))
        self._count_lbl.setStyleSheet(f"color: {theme.TURQUOISE}; background: transparent;")
        head.addWidget(self._count_lbl)
        head.addStretch(1)
        self._toggle_btn = QPushButton("Tout désélectionner")
        self._toggle_btn.setStyleSheet(theme.qss_button_ghost())
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.hide()
        self._toggle_btn.clicked.connect(self._toggle_all)
        head.addWidget(self._toggle_btn)
        self.body_layout.addLayout(head)

        # Scrollable container for the rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._tracks_layout = QVBoxLayout(container)
        self._tracks_layout.setContentsMargins(0, 4, 0, 4)
        self._tracks_layout.setSpacing(4)
        self._tracks_layout.addStretch(1)

        self._empty_lbl = QLabel("Colle une URL et clique sur Analyser pour découvrir les morceaux.")
        self._empty_lbl.setFont(theme.font("body", 13, italic=True))
        self._empty_lbl.setStyleSheet(
            f"color: {theme.FG_DIM}; background: transparent; padding: 30px;"
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setWordWrap(True)
        # Insert before the stretch
        self._tracks_layout.insertWidget(0, self._empty_lbl)

        scroll.setWidget(container)
        self.body_layout.addWidget(scroll, stretch=1)

    def _build_destination_section(self) -> None:
        self.body_layout.addWidget(self._section_label("Dossier de destination"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self._dest_input = QLineEdit()
        self._dest_input.setPlaceholderText("Choisis un dossier…")
        self._dest_input.setStyleSheet(theme.qss_input())
        self._dest_input.setText(self._cfg.get("dernier_dossier", ""))
        row.addWidget(self._dest_input, stretch=1)

        browse = QPushButton("Parcourir")
        browse.setStyleSheet(theme.qss_button_ghost())
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse_destination)
        row.addWidget(browse)

        self.body_layout.addLayout(row)

    def _build_actions_section(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._download_btn = QPushButton("⬇   Télécharger")
        self._download_btn.setStyleSheet(theme.qss_button_primary())
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._start_download)
        row.addWidget(self._download_btn)

        self._cancel_btn = QPushButton("✕   Annuler")
        self._cancel_btn.setStyleSheet(theme.qss_button_ghost())
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_download)
        row.addWidget(self._cancel_btn)

        row.addStretch(1)

        self._counter_lbl = QLabel("")
        self._counter_lbl.setFont(theme.font("mono", 13, QFont.Weight.DemiBold))
        self._counter_lbl.setStyleSheet(f"color: {theme.SUCCESS}; background: transparent;")
        row.addWidget(self._counter_lbl)

        self.body_layout.addLayout(row)

    # ── Signal wiring ────────────────────────────────────────────────────────
    def _wire_signals(self) -> None:
        self.preview_ready.connect(self._on_preview_ready)
        self.preview_failed.connect(self._on_preview_failed)
        self.row_progress.connect(self._on_row_progress)
        self.row_speed.connect(self._on_row_speed)
        self.counter_changed.connect(self._on_counter_changed)
        self.download_done.connect(self._on_download_done)
        self.download_cancelled.connect(self._on_download_cancelled)

    # ── Clipboard auto-detect on focus ───────────────────────────────────────
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._check_clipboard()

    def _check_clipboard(self) -> None:
        try:
            from PySide6.QtGui import QGuiApplication
            if self._url_input.text().strip():
                return
            cb = (QGuiApplication.clipboard().text() or "").strip()
            if cb == self._last_clipboard or not cb.startswith("http"):
                return
            self._last_clipboard = cb
            self._url_input.setText(cb)
            self.set_status("URL détectée dans le presse-papiers", theme.SUCCESS)
        except Exception:
            pass

    # ── Preview / analyse ────────────────────────────────────────────────────
    def _fetch_preview(self) -> None:
        url = self._url_input.text().strip()
        if not _validate_url(url):
            QMessageBox.warning(self, "URL invalide",
                                "Colle une URL valide avant d'analyser.")
            return

        self._reset_tracks()
        self._download_btn.setEnabled(False)
        self._analyze_btn.setEnabled(False)
        self.set_status("Analyse en cours…", theme.TURQUOISE)

        def run():
            try:
                opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    tracks = [
                        {"title": e.get("title", "Titre inconnu"),
                         "duration": e.get("duration"),
                         "url": e.get("url") or e.get("webpage_url") or url}
                        for e in info["entries"] if e
                    ]
                else:
                    tracks = [{"title": info.get("title", "Titre inconnu"),
                               "duration": info.get("duration"),
                               "url": url}]
                self.preview_ready.emit(tracks)
            except Exception as e:
                self.preview_failed.emit(str(e))

        threading.Thread(target=run, daemon=True).start()

    def _reset_tracks(self) -> None:
        for row in self._track_rows:
            self._tracks_layout.removeWidget(row)
            row.deleteLater()
        self._track_rows.clear()
        self._tracks = []
        self._count_lbl.setText("")
        self._toggle_btn.hide()
        self._empty_lbl.show()

    def _on_preview_ready(self, tracks: list) -> None:
        self._tracks = tracks
        self._empty_lbl.hide()

        dest = self._dest_input.text().strip()
        existing: set[str] = set()
        if dest:
            p = Path(dest)
            if p.exists():
                existing = {f.stem.lower() for f in p.iterdir() if f.is_file()}

        for i, track in enumerate(self._tracks):
            is_dup = any(track["title"].lower()[:40] in s for s in existing)
            row = _TrackRow(i, track["title"], track["duration"], is_dup)
            # Insert before the trailing stretch (last item).
            self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
            self._track_rows.append(row)

        n = len(self._tracks)
        self._count_lbl.setText(f"· {n} morceau{'x' if n > 1 else ''}")
        self.set_status(
            f"{'Playlist' if n > 1 else 'Vidéo unique'} — prêt à télécharger",
            theme.SUCCESS,
        )
        self._download_btn.setEnabled(True)
        self._analyze_btn.setEnabled(True)
        self._toggle_btn.setText("Tout désélectionner")
        self._toggle_btn.show()

    def _on_preview_failed(self, msg: str) -> None:
        self.set_status(f"Erreur : {msg}", theme.ERROR)
        self._analyze_btn.setEnabled(True)

    def _toggle_all(self) -> None:
        all_checked = all(r.is_checked() for r in self._track_rows)
        for r in self._track_rows:
            r.set_checked(not all_checked)
        self._toggle_btn.setText(
            "Tout sélectionner" if all_checked else "Tout désélectionner"
        )

    # ── Destination ──────────────────────────────────────────────────────────
    def _browse_destination(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Choisir un dossier de destination",
            self._dest_input.text().strip() or str(Path.home()),
        )
        if d:
            self._dest_input.setText(d)
            settings_store.save(TOOL_ID, {"dernier_dossier": d})

    # ── Download ─────────────────────────────────────────────────────────────
    def _build_ydl_opts(self, dossier: str, idx: int, fmt: str, quality: str) -> dict:
        codec = FORMAT_CODEC[fmt]
        embed = fmt in SUPPORTS_THUMBNAIL

        def hook(d, idx=idx):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                dl = d.get("downloaded_bytes", 0)
                speed = d.get("speed")
                if total:
                    self.row_progress.emit(idx, int(dl / total * 100))
                if speed:
                    self.row_speed.emit(idx, _format_speed(speed))
            elif d["status"] == "finished":
                self.row_progress.emit(idx, 100)
                self.row_speed.emit(idx, "")

        pp = [{"key": "FFmpegExtractAudio", "preferredcodec": codec}]
        if fmt == "MP3":
            pp[0]["preferredquality"] = quality
        pp.append({"key": "FFmpegMetadata", "add_metadata": True})
        if embed:
            pp.append({"key": "EmbedThumbnail"})

        return {
            "format": "bestaudio/best",
            "postprocessors": pp,
            "outtmpl": str(Path(dossier).resolve() / "%(title)s.%(ext)s"),
            "progress_hooks": [hook],
            "ffmpeg_location": _resource_path("ffmpeg_bin"),
            "quiet": True,
            "windowsfilenames": True,
            "writethumbnail": embed,
        }

    def _start_download(self) -> None:
        dossier = self._dest_input.text().strip()
        if not dossier:
            QMessageBox.warning(self, "Attention", "Choisis un dossier de destination !")
            return
        ok, err = _check_destination(dossier)
        if not ok:
            QMessageBox.critical(self, "Dossier inaccessible", err)
            return
        selected = [(i, t) for i, t in enumerate(self._tracks)
                    if self._track_rows[i].is_checked()]
        if not selected:
            QMessageBox.warning(self, "Attention", "Aucun morceau sélectionné !")
            return

        fmt = self._fmt_pill.value()
        quality = self._qual_pill.value() or "192"
        workers = int(self._workers_pill.value() or "2")
        settings_store.save(TOOL_ID, {
            "dernier_dossier": dossier, "format": fmt,
            "quality": quality, "workers": workers,
        })

        self._cancel_flag.clear()
        self._download_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._analyze_btn.setEnabled(False)
        self._counter_lbl.setText(f"0 / {len(selected)}")
        self.set_status(f"Téléchargement ({workers} en parallèle)…", theme.TURQUOISE)

        def run():
            done, errors = [0], []

            def do_one(args):
                i, track = args
                if self._cancel_flag.is_set():
                    return False, track["title"], None
                self.row_progress.emit(i, 0)
                try:
                    opts = self._build_ydl_opts(dossier, i, fmt, quality)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([track["url"]])
                    _append_history(track["title"], track["url"], dossier, fmt)
                    return True, track["title"], None
                except Exception as e:
                    return False, track["title"], str(e)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(do_one, item): item for item in selected}
                for future in as_completed(futures):
                    success, title, err = future.result()
                    if success:
                        done[0] += 1
                        self.counter_changed.emit(done[0], len(selected))
                    elif err:
                        errors.append(f"{title}: {err}")
                    if self._cancel_flag.is_set():
                        for f in futures:
                            f.cancel()
                        break

            if self._cancel_flag.is_set():
                self.download_cancelled.emit()
            else:
                self.download_done.emit(done[0], errors)

        threading.Thread(target=run, daemon=True).start()

    def _cancel_download(self) -> None:
        self._cancel_flag.set()
        self._cancel_btn.setEnabled(False)

    def _on_row_progress(self, idx: int, pct: int) -> None:
        if 0 <= idx < len(self._track_rows):
            self._track_rows[idx].set_progress(pct)

    def _on_row_speed(self, idx: int, text: str) -> None:
        if 0 <= idx < len(self._track_rows):
            self._track_rows[idx].set_speed(text)

    def _on_counter_changed(self, done: int, total: int) -> None:
        self._counter_lbl.setText(f"{done} / {total}")

    def _on_download_done(self, done: int, errors: list) -> None:
        if errors:
            self.set_status(
                f"{done} téléchargé(s), {len(errors)} erreur(s)", theme.WARNING
            )
        else:
            self.set_status(
                f"{done} morceau{'x' if done > 1 else ''} téléchargé"
                f"{'s' if done > 1 else ''} !",
                theme.SUCCESS,
            )
            self._notify(done)
        self._download_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._analyze_btn.setEnabled(True)

    def _on_download_cancelled(self) -> None:
        self.set_status("Annulé", theme.ERROR)
        self._download_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._analyze_btn.setEnabled(True)

    def _notify(self, count: int) -> None:
        msg = f"MyFileConverter – {count} morceau(x) téléchargé(s) !"
        try:
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                " Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                "$t = [Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText01);"
                f'$t.SelectSingleNode("//text[@id=1]").InnerText = "{msg}";'
                "$n = [Windows.UI.Notifications.ToastNotification]::new($t);"
                '[Windows.UI.Notifications.ToastNotificationManager]::'
                'CreateToastNotifier("MyFileConverter").Show($n);'
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                creationflags=0x08000000,
            )
        except Exception:
            pass

    # ── History dialog ───────────────────────────────────────────────────────
    def _show_history(self) -> None:
        history = _load_history()
        dlg = _HistoryDialog(history, self)
        dlg.exec()


# ─────────────────────────────────────────────────────────────────────────────
# History dialog
# ─────────────────────────────────────────────────────────────────────────────

class _HistoryDialog(QDialog):
    def __init__(self, history: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(760, 460)

        outer = QFrame(self)
        outer.setObjectName("HistoryCard")
        outer.setGeometry(0, 0, 760, 460)
        outer.setStyleSheet(f"""
            #HistoryCard {{
                background-color: {theme.INK_DEEP};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.4)};
                border-radius: 22px;
            }}
        """)

        col = QVBoxLayout(outer)
        col.setContentsMargins(28, 22, 28, 22)
        col.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("Historique des téléchargements")
        title.setFont(theme.font("display", 22, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        head.addWidget(title)
        head.addStretch(1)
        close = QPushButton("✕")
        close.setFixedSize(34, 34)
        close.setStyleSheet(theme.qss_close_btn())
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        head.addWidget(close)
        col.addLayout(head)

        if not history:
            empty = QLabel("Aucun téléchargement enregistré.")
            empty.setFont(theme.font("body", 13, italic=True))
            empty.setStyleSheet(f"color: {theme.FG_MUTED}; padding: 60px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(empty)
            col.addStretch(1)
            return

        table = QTableWidget(len(history), 4)
        table.setHorizontalHeaderLabels(["Date", "Titre", "Format", "Dossier"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {theme.rgba(theme.INK_DEEPEST, 0.4)};
                color: {theme.FG};
                border: 1px solid {theme.rgba(theme.TURQUOISE, 0.15)};
                border-radius: 10px;
                gridline-color: transparent;
                outline: 0;
            }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{
                background-color: {theme.rgba(theme.TURQUOISE, 0.25)};
                color: {theme.FG};
            }}
            QHeaderView::section {{
                background-color: {theme.rgba(theme.INK, 0.7)};
                color: {theme.FG_MUTED};
                padding: 8px;
                border: none;
                font-weight: 600;
            }}
        """)
        for r, e in enumerate(history):
            table.setItem(r, 0, QTableWidgetItem(e.get("date", "")))
            table.setItem(r, 1, QTableWidgetItem(e.get("title", "")))
            table.setItem(r, 2, QTableWidgetItem(e.get("format", "")))
            table.setItem(r, 3, QTableWidgetItem(e.get("folder", "")))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        col.addWidget(table, stretch=1)

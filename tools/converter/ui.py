import json
import os
import subprocess
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import yt_dlp

import core.settings as settings_store
from core.base_tool import BaseTool

TOOL_ID = "converter"

FORMAT_CODEC       = {"MP3": "mp3", "FLAC": "flac", "M4A": "m4a", "WAV": "wav", "OGG": "vorbis"}
SUPPORTS_THUMBNAIL = {"MP3", "M4A"}


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
        return f"{bps/1_000_000:.1f} MB/s"
    return f"{bps/1_000:.0f} KB/s"


def _load_history() -> list:
    hf = settings_store.history_file(TOOL_ID)
    if hf.exists():
        try:
            with open(hf, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _append_history(title: str, url: str, folder: str, fmt: str):
    hf = settings_store.history_file(TOOL_ID)
    h = _load_history()
    h.insert(0, {"title": title, "url": url, "folder": folder,
                 "format": fmt, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(hf, "w", encoding="utf-8") as f:
        json.dump(h[:200], f, ensure_ascii=False, indent=2)


class ConverterTool(BaseTool):
    def __init__(self, parent):
        self._cfg           = settings_store.load(TOOL_ID)
        self._tracks        = []
        self._check_vars    = []
        self._prog_bars     = []
        self._speed_labels  = []
        self._annuler_flag  = threading.Event()
        self._last_cb       = ""
        super().__init__(parent, "MyFileConverter", accent="#e84393",
                         width=700, height=700)

    # ── build ────────────────────────────────────────────────────────────────────
    def build(self):
        self._build_url_section()
        self._build_options_row()
        tk.Frame(self.win, bg=self.BG3, height=1).pack(fill="x", padx=24)
        self._build_track_list()
        tk.Frame(self.win, bg=self.BG3, height=1).pack(fill="x", padx=24, pady=8)
        self._build_destination_section()
        self._build_action_buttons()
        self._make_status_bar("Colle une URL et clique sur Analyser")
        self.win.bind("<FocusIn>", self._check_clipboard)

    def _build_url_section(self):
        sec = tk.Frame(self.win, bg=self.BG)
        sec.pack(fill="x", padx=24, pady=(12, 10))
        tk.Label(sec, text="URL", bg=self.BG, fg=self.FG2,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(sec, bg=self.BG2)
        row.pack(fill="x")
        self._entry_url = tk.Entry(row, bg=self.BG2, fg=self.FG,
                                   insertbackground=self.FG,
                                   relief="flat", font=("Segoe UI", 10), bd=0)
        self._entry_url.pack(side="left", fill="x", expand=True, ipady=8, padx=(12, 0))
        self._btn_preview = tk.Button(
            row, text="Analyser →", command=self._fetch_preview,
            bg=self.accent, fg=self.FG, relief="flat",
            padx=16, pady=8, cursor="hand2", font=("Segoe UI", 9, "bold"), bd=0,
            activebackground=self.BG3, activeforeground=self.FG)
        self._btn_preview.pack(side="left", padx=(8, 0))

    def _build_options_row(self):
        tk.Frame(self.win, bg=self.BG3, height=1).pack(fill="x", padx=24, pady=(6, 0))
        row = tk.Frame(self.win, bg=self.BG)
        row.pack(fill="x", padx=24, pady=10)

        def combo(parent, label, values, default, width=8):
            f = tk.Frame(parent, bg=self.BG)
            f.pack(side="left", padx=(0, 24))
            tk.Label(f, text=label, bg=self.BG, fg=self.FG2,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            c = ttk.Combobox(f, values=values, state="readonly",
                             width=width, font=("Segoe UI", 9))
            c.set(default)
            c.pack()
            return c

        self._combo_fmt  = combo(row, "FORMAT",
                                  ["MP3", "FLAC", "M4A", "WAV", "OGG"],
                                  self._cfg.get("format", "MP3"))
        self._combo_qual = combo(row, "QUALITÉ (MP3)", ["128", "192", "320"],
                                  self._cfg.get("quality", "192"))
        self._combo_workers = combo(row, "EN PARALLÈLE", ["1", "2", "3", "4", "5"],
                                    str(self._cfg.get("workers", 2)), width=4)
        self._combo_fmt.bind("<<ComboboxSelected>>", self._on_format_change)
        self._on_format_change()

        tk.Button(row, text="Historique", command=self._show_history,
                  bg=self.BG3, fg=self.FG2, relief="flat", padx=10, pady=4,
                  font=("Segoe UI", 8), cursor="hand2", bd=0).pack(side="right")

    def _on_format_change(self, *_):
        state = "readonly" if self._combo_fmt.get() == "MP3" else "disabled"
        self._combo_qual.config(state=state)

    def _build_track_list(self):
        hdr = tk.Frame(self.win, bg=self.BG)
        hdr.pack(fill="x", padx=24, pady=(8, 4))
        tk.Label(hdr, text="MORCEAUX", bg=self.BG, fg=self.FG2,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._label_count = tk.Label(hdr, text="", bg=self.BG, fg=self.accent,
                                      font=("Segoe UI", 8, "bold"))
        self._label_count.pack(side="left", padx=8)

        fc = tk.Frame(self.win, bg=self.BG)
        fc.pack(fill="both", expand=True, padx=24)
        self._canvas = tk.Canvas(fc, bg=self.BG, highlightthickness=0)
        sb = ttk.Scrollbar(fc, orient="vertical", command=self._canvas.yview,
                            style="Tool.Vertical.TScrollbar")
        self._frame_tracks = tk.Frame(self._canvas, bg=self.BG)
        self._frame_tracks.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._frame_tracks, anchor="nw", width=640)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", self._on_scroll))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        self._frame_check_btns = tk.Frame(self.win, bg=self.BG)
        self._btn_toggle = tk.Button(
            self._frame_check_btns, text="Tout désélectionner",
            command=self._toggle_all, bg=self.BG3, fg=self.FG2,
            relief="flat", padx=10, pady=4, font=("Segoe UI", 8), cursor="hand2", bd=0)
        self._btn_toggle.pack(side="left")

    def _on_scroll(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _build_destination_section(self):
        sec = tk.Frame(self.win, bg=self.BG)
        sec.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(sec, text="DOSSIER DE DESTINATION", bg=self.BG, fg=self.FG2,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(sec, bg=self.BG2)
        row.pack(fill="x")
        self._entry_dossier = tk.Entry(row, bg=self.BG2, fg=self.FG,
                                        insertbackground=self.FG,
                                        relief="flat", font=("Segoe UI", 10), bd=0)
        self._entry_dossier.pack(side="left", fill="x", expand=True, ipady=8, padx=(12, 0))
        self._entry_dossier.insert(0, self._cfg.get("dernier_dossier", ""))
        tk.Button(row, text="Parcourir", command=self._choisir_dossier,
                  bg=self.BG3, fg=self.FG2, relief="flat", padx=12, pady=8,
                  font=("Segoe UI", 8), cursor="hand2", bd=0).pack(side="left", padx=4)

    def _build_action_buttons(self):
        row = tk.Frame(self.win, bg=self.BG)
        row.pack(fill="x", padx=24, pady=(0, 10))
        self._btn_dl = tk.Button(
            row, text="⬇  Télécharger", command=self._telecharger,
            bg=self.accent, fg=self.FG, relief="flat", padx=20, pady=10,
            cursor="hand2", font=("Segoe UI", 10, "bold"), state="disabled", bd=0)
        self._btn_dl.pack(side="left", padx=(0, 8))
        self._btn_cancel = tk.Button(
            row, text="✕  Annuler", command=self._annuler,
            bg=self.BG3, fg=self.FG2, relief="flat", padx=16, pady=10,
            cursor="hand2", font=("Segoe UI", 10), state="disabled", bd=0)
        self._btn_cancel.pack(side="left")
        self._label_compteur = tk.Label(row, text="", bg=self.BG, fg=self.VERT,
                                         font=("Segoe UI", 10, "bold"))
        self._label_compteur.pack(side="right")

    # ── Clipboard ────────────────────────────────────────────────────────────────
    def _check_clipboard(self, *_):
        try:
            if self._entry_url.get().strip():
                return
            cb = self.win.clipboard_get().strip()
            if cb == self._last_cb or not cb.startswith("http"):
                return
            self._last_cb = cb
            self._entry_url.delete(0, tk.END)
            self._entry_url.insert(0, cb)
            self.set_status("URL détectée dans le presse-papiers", self.VERT)
        except Exception:
            pass

    # ── Preview ──────────────────────────────────────────────────────────────────
    def _fetch_preview(self):
        url = self._entry_url.get().strip()
        if not _validate_url(url):
            messagebox.showwarning("URL invalide", "Colle une URL valide avant d'analyser.",
                                   parent=self.win)
            return
        self._tracks, self._check_vars, self._prog_bars, self._speed_labels = [], [], [], []
        for w in self._frame_tracks.winfo_children():
            w.destroy()
        self._btn_dl.config(state="disabled")
        self._btn_preview.config(state="disabled")
        self.set_status("Analyse en cours...", self.accent)

        def run():
            try:
                opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    self._tracks = [
                        {"title": e.get("title", "Titre inconnu"),
                         "duration": e.get("duration"),
                         "url": e.get("url") or e.get("webpage_url") or url}
                        for e in info["entries"] if e
                    ]
                else:
                    self._tracks = [{"title": info.get("title", "Titre inconnu"),
                                     "duration": info.get("duration"), "url": url}]
                self.win.after(0, self._afficher_tracks)
            except Exception as e:
                self.win.after(0, lambda: self.set_status(f"Erreur : {e}", self.ROUGE))
                self.win.after(0, lambda: self._btn_preview.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _afficher_tracks(self):
        self._check_vars, self._prog_bars, self._speed_labels = [], [], []
        for w in self._frame_tracks.winfo_children():
            w.destroy()

        dossier = self._entry_dossier.get().strip()
        existing = set()
        if dossier:
            p = Path(dossier)
            if p.exists():
                existing = {f.stem.lower() for f in p.iterdir() if f.is_file()}

        for i, track in enumerate(self._tracks):
            var = tk.BooleanVar(value=True)
            self._check_vars.append(var)
            is_dup = any(track["title"].lower()[:40] in s for s in existing)
            row_bg = self.BG3 if i % 2 == 0 else self.BG2
            row = tk.Frame(self._frame_tracks, bg=row_bg)
            row.pack(fill="x", pady=1)

            tk.Checkbutton(row, variable=var, bg=row_bg, activebackground=row_bg,
                           selectcolor=self.BG, fg=self.FG, cursor="hand2"
                           ).pack(side="left", padx=(8, 4), pady=6)
            tk.Label(row, text=f"{i+1:02d}", bg=row_bg, fg=self.FG2,
                     font=("Consolas", 9)).pack(side="left", padx=(0, 8))

            titre = track["title"][:46] + "…" if len(track["title"]) > 46 else track["title"]
            tag = "  [déjà dl]" if is_dup else ""
            tk.Label(row, text=titre + tag, bg=row_bg,
                     fg=self.FG2 if is_dup else self.FG,
                     font=("Segoe UI", 9), anchor="w"
                     ).pack(side="left", fill="x", expand=True)

            spd = tk.Label(row, text="", bg=row_bg, fg=self.JAUNE,
                           font=("Consolas", 8), width=9)
            spd.pack(side="right", padx=(0, 2))
            self._speed_labels.append(spd)

            tk.Label(row, text=_format_duration(track["duration"]),
                     bg=row_bg, fg=self.FG2, font=("Consolas", 9)
                     ).pack(side="right", padx=4)

            pb = ttk.Progressbar(row, length=70, mode="determinate",
                                 style=self._pb_style)
            pb.pack(side="right", padx=4)
            self._prog_bars.append(pb)

        n = len(self._tracks)
        self._label_count.config(text=f"{n} morceau{'x' if n > 1 else ''}")
        self.set_status(
            f"{'Playlist' if n > 1 else 'Vidéo unique'} — prêt à télécharger", self.VERT)
        self._btn_dl.config(state="normal")
        self._btn_preview.config(state="normal")
        self._btn_toggle.config(text="Tout désélectionner")
        self._frame_check_btns.pack(pady=(0, 6))
        self._canvas.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    # ── Download ─────────────────────────────────────────────────────────────────
    def _build_ydl_opts(self, dossier: str, pb, spd, fmt: str, quality: str) -> dict:
        codec = FORMAT_CODEC[fmt]
        embed = fmt in SUPPORTS_THUMBNAIL

        def hook(d, p=pb, s=spd):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                dl, speed = d.get("downloaded_bytes", 0), d.get("speed")
                if total:
                    self.win.after(0, lambda v=dl / total * 100: p.config(value=v))
                if speed:
                    self.win.after(0, lambda sp=_format_speed(speed): s.config(text=sp))
            elif d["status"] == "finished":
                self.win.after(0, lambda: p.config(value=100))
                self.win.after(0, lambda: s.config(text=""))

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

    def _telecharger(self):
        dossier = self._entry_dossier.get().strip()
        if not dossier:
            messagebox.showwarning("Attention", "Choisis un dossier de destination !",
                                   parent=self.win)
            return
        ok, err = _check_destination(dossier)
        if not ok:
            messagebox.showerror("Dossier inaccessible", err, parent=self.win)
            return
        selected = [(i, t) for i, t in enumerate(self._tracks) if self._check_vars[i].get()]
        if not selected:
            messagebox.showwarning("Attention", "Aucun morceau sélectionné !", parent=self.win)
            return

        fmt     = self._combo_fmt.get()
        quality = self._combo_qual.get()
        workers = int(self._combo_workers.get())
        settings_store.save(TOOL_ID, {"dernier_dossier": dossier, "format": fmt,
                                      "quality": quality, "workers": workers})
        self._annuler_flag.clear()
        self._btn_dl.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._btn_preview.config(state="disabled")
        self._label_compteur.config(text=f"0 / {len(selected)}")
        self.set_status(f"Téléchargement ({workers} en parallèle)...", self.accent)

        def run():
            done, errors = [0], []

            def do_one(args):
                i, track = args
                if self._annuler_flag.is_set():
                    return False, track["title"], None
                self.win.after(0, lambda p=self._prog_bars[i]: p.config(value=0))
                try:
                    opts = self._build_ydl_opts(
                        dossier, self._prog_bars[i], self._speed_labels[i], fmt, quality)
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
                        self.win.after(0, lambda d=done[0], t=len(selected):
                                       self._label_compteur.config(text=f"{d} / {t}"))
                    elif err:
                        errors.append(f"{title}: {err}")
                    if self._annuler_flag.is_set():
                        for f in futures:
                            f.cancel()
                        break

            if self._annuler_flag.is_set():
                self.win.after(0, lambda: self.set_status("Annulé", self.ROUGE))
            elif errors:
                self.win.after(0, lambda: self.set_status(
                    f"{done[0]} téléchargé(s), {len(errors)} erreur(s)", self.JAUNE))
            else:
                d = done[0]
                self.win.after(0, lambda: self.set_status(
                    f"{d} morceau{'x' if d > 1 else ''} téléchargé{'s' if d > 1 else ''} !",
                    self.VERT))
                self._notify(d)

            self.win.after(0, lambda: self._btn_dl.config(state="normal"))
            self.win.after(0, lambda: self._btn_cancel.config(state="disabled"))
            self.win.after(0, lambda: self._btn_preview.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _notify(self, count: int):
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
                creationflags=0x08000000)
        except Exception:
            pass

    def _annuler(self):
        self._annuler_flag.set()
        self._btn_cancel.config(state="disabled")

    def _choisir_dossier(self):
        d = filedialog.askdirectory(parent=self.win)
        if d:
            self._entry_dossier.delete(0, tk.END)
            self._entry_dossier.insert(0, d)
            settings_store.save(TOOL_ID, {"dernier_dossier": d})

    def _toggle_all(self):
        all_checked = all(v.get() for v in self._check_vars)
        for v in self._check_vars:
            v.set(not all_checked)
        self._btn_toggle.config(
            text="Tout sélectionner" if all_checked else "Tout désélectionner")

    # ── History ──────────────────────────────────────────────────────────────────
    def _show_history(self):
        history = _load_history()
        win = tk.Toplevel(self.win)
        win.title("Historique")
        win.geometry("720x380")
        win.configure(bg=self.BG)
        win.transient(self.win)
        tk.Label(win, text="Historique des téléchargements", bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 12, "bold")).pack(padx=16, pady=(12, 8), anchor="w")
        if not history:
            tk.Label(win, text="Aucun téléchargement enregistré.", bg=self.BG, fg=self.FG2,
                     font=("Segoe UI", 10)).pack(pady=30)
            return
        sty = ttk.Style(win)
        sty.configure("H.Treeview", background=self.BG2, foreground=self.FG,
                      fieldbackground=self.BG2, rowheight=24, font=("Segoe UI", 9))
        sty.configure("H.Treeview.Heading", background=self.BG3, foreground=self.FG2,
                      font=("Segoe UI", 8, "bold"))
        sty.map("H.Treeview", background=[("selected", self.accent)])
        cols = ("date", "title", "format", "folder")
        tree = ttk.Treeview(win, columns=cols, show="headings", style="H.Treeview")
        for col, label, w in [("date", "Date", 120), ("title", "Titre", 250),
                               ("format", "Format", 60), ("folder", "Dossier", 240)]:
            tree.heading(col, text=label)
            tree.column(col, width=w, anchor="w")
        for e in history:
            tree.insert("", "end", values=(
                e.get("date", ""), e.get("title", ""),
                e.get("format", ""), e.get("folder", "")))
        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=(0, 16))
        sb.pack(side="right", fill="y", pady=(0, 16), padx=(0, 8))

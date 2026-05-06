import os
import sys
import threading
import tkinter as tk
from pathlib import Path

from core.updater import check_update, download_and_update, has_update, load_local_version
from tools.registry import TOOLS

# ─── Config ──────────────────────────────────────────────────────────────────────
GITHUB_REPO   = "LucasOnCode/MyHub53"   # ← à renseigner avant de builder
VERSION_FILE  = Path(__file__).parent / "version.txt"
LOCAL_VERSION = load_local_version(VERSION_FILE)

# ─── Colors ──────────────────────────────────────────────────────────────────────
BG    = "#0f0f17"
BG2   = "#1a1a2e"
BG3   = "#222235"
FG    = "#f0f0f5"
FG2   = "#8888aa"
VERT  = "#22d3a5"
ROUGE = "#ef4444"

# ─── Layout constants ────────────────────────────────────────────────────────────
COLS   = 2
TILE_W = 230
TILE_H = 200
PAD    = 20


def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


# ─── Window ───────────────────────────────────────────────────────────────────────
rows   = max(1, (len(TOOLS) + COLS - 1) // COLS)
win_w  = COLS * TILE_W + (COLS + 1) * PAD
win_h  = 74 + rows * (TILE_H + PAD) + PAD + 36

fenetre = tk.Tk()
fenetre.title("Mon Hub")
fenetre.geometry(f"{win_w}x{win_h}")
fenetre.resizable(False, False)
fenetre.configure(bg=BG)

try:
    fenetre.iconbitmap(resource_path("icone.ico"))
except Exception:
    pass

# ─── Header ──────────────────────────────────────────────────────────────────────
header = tk.Frame(fenetre, bg=BG2, pady=12)
header.pack(fill="x")

tk.Label(header, text="💝  Mon Hub", bg=BG2, fg=FG,
         font=("Segoe UI", 15, "bold")).pack(side="left", padx=18)

lbl_version = tk.Label(header, text=f"v{LOCAL_VERSION}", bg=BG2, fg=FG2,
                        font=("Segoe UI", 9))
lbl_version.pack(side="left")

lbl_badge = tk.Label(header, text="", bg=BG2, fg=VERT,
                     font=("Segoe UI", 8, "bold"))
lbl_badge.pack(side="right", padx=(0, 8))

btn_update = tk.Button(header, text="Vérifier les mises à jour",
                        command=lambda: _check_for_updates(silent=False),
                        bg=BG3, fg=FG2, relief="flat", padx=10, pady=4,
                        font=("Segoe UI", 8), cursor="hand2", bd=0)
btn_update.pack(side="right", padx=(0, 6))

# ─── Tile grid ───────────────────────────────────────────────────────────────────
grid = tk.Frame(fenetre, bg=BG)
grid.pack(fill="both", expand=True, padx=PAD, pady=PAD)

for c in range(COLS):
    grid.columnconfigure(c, weight=1)


def _make_tile(tool, row: int, col: int):
    tile = tk.Frame(grid, bg=BG2, width=TILE_W, height=TILE_H, cursor="hand2")
    tile.grid(row=row, column=col, padx=(0, PAD if col < COLS - 1 else 0),
              pady=(0, PAD), sticky="nsew")
    tile.pack_propagate(False)

    tk.Frame(tile, bg=tool.accent, height=3).pack(fill="x")

    icon_lbl = tk.Label(tile, text=tool.icon, bg=BG2, font=("Segoe UI", 36))
    name_lbl = tk.Label(tile, text=tool.name, bg=BG2, fg=FG,
                         font=("Segoe UI", 10, "bold"))
    desc_lbl = tk.Label(tile, text=tool.description, bg=BG2, fg=FG2,
                         font=("Segoe UI", 8), wraplength=TILE_W - 24)
    icon_lbl.pack(pady=(18, 4))
    name_lbl.pack()
    desc_lbl.pack(pady=(4, 0))

    hover_targets = [tile, icon_lbl, name_lbl, desc_lbl]

    def on_enter(e, ws=hover_targets):
        for w in ws:
            w.config(bg=BG3)

    def on_leave(e, ws=hover_targets):
        for w in ws:
            w.config(bg=BG2)

    def on_click(e, tc=tool):
        tc.klass(fenetre)

    for w in hover_targets:
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        w.bind("<Button-1>", on_click)


for idx, tool in enumerate(TOOLS):
    r, c = divmod(idx, COLS)
    _make_tile(tool, r, c)

# ─── Status bar ──────────────────────────────────────────────────────────────────
lbl_status = tk.Label(fenetre, text="", bg=BG, fg=FG2, font=("Segoe UI", 8))
lbl_status.pack(pady=(0, 8))

# ─── Update logic ────────────────────────────────────────────────────────────────
_remote_version = [None]
_download_url   = [None]


def _check_for_updates(silent: bool = True):
    btn_update.config(state="disabled")
    if not silent:
        lbl_status.config(text="Vérification des mises à jour...", fg=FG2)

    def run():
        version, url = check_update(GITHUB_REPO)
        _remote_version[0] = version
        _download_url[0]   = url
        fenetre.after(0, lambda: _on_check_done(version, url, silent))

    threading.Thread(target=run, daemon=True).start()


def _on_check_done(version, url, silent: bool):
    btn_update.config(state="normal")
    if not version:
        if not silent:
            lbl_status.config(text="Impossible de vérifier les mises à jour.", fg=ROUGE)
        return

    if has_update(LOCAL_VERSION, version):
        lbl_badge.config(text=f"▲ v{version} dispo")
        btn_update.config(text=f"Installer v{version}", bg=VERT, fg=BG,
                          command=_do_update)
        lbl_status.config(text=f"Nouvelle version disponible : v{version}", fg=VERT)
    else:
        if not silent:
            lbl_status.config(text="Vous êtes à jour !", fg=VERT)


def _do_update():
    url = _download_url[0]
    if not url:
        return
    btn_update.config(state="disabled", text="Téléchargement en cours...")

    def run():
        try:
            def progress(pct: int):
                fenetre.after(0, lambda p=pct:
                              btn_update.config(text=f"Téléchargement... {p}%"))
            download_and_update(url, progress)
        except RuntimeError as e:
            fenetre.after(0, lambda: lbl_status.config(text=str(e), fg=ROUGE))
            fenetre.after(0, lambda: btn_update.config(state="normal"))

    threading.Thread(target=run, daemon=True).start()


# Vérification silencieuse 3 s après le démarrage
fenetre.after(3000, lambda: _check_for_updates(silent=True))

fenetre.mainloop()

import threading
import tkinter as tk
from tkinter import ttk


class BaseTool:
    BG    = "#0f0f17"
    BG2   = "#1a1a2e"
    BG3   = "#222235"
    FG    = "#f0f0f5"
    FG2   = "#8888aa"
    VERT  = "#22d3a5"
    ROUGE = "#ef4444"
    JAUNE = "#f59e0b"

    def __init__(self, parent: tk.Misc, name: str, accent: str,
                 width: int = 700, height: int = 680):
        self.accent = accent
        self.parent = parent
        self._label_statut = None

        self.win = tk.Toplevel(parent)
        self.win.title(name)
        self.win.geometry(f"{width}x{height}")
        self.win.resizable(False, False)
        self.win.configure(bg=self.BG)
        self.win.transient(parent)

        self._pb_style = f"{type(self).__name__}.Horizontal.TProgressbar"
        style = ttk.Style(self.win)
        style.theme_use("default")
        style.configure(self._pb_style,
                        troughcolor=self.BG2, background=accent, thickness=5)
        style.configure("Tool.Vertical.TScrollbar",
                        background=self.BG3, troughcolor=self.BG2,
                        bordercolor=self.BG2, arrowcolor=self.FG2)

        self._build_header(name)
        self.build()

    def _build_header(self, name: str):
        h = tk.Frame(self.win, bg=self.BG2, pady=10)
        h.pack(fill="x")
        bar = tk.Frame(h, bg=self.accent, width=4)
        bar.pack(side="left", fill="y", padx=(0, 12))
        tk.Label(h, text=name, bg=self.BG2, fg=self.FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(h, text="✕", command=self.win.destroy,
                  bg=self.BG2, fg=self.FG2, relief="flat",
                  font=("Segoe UI", 11), cursor="hand2", bd=0,
                  activebackground=self.BG2, activeforeground=self.ROUGE
                  ).pack(side="right", padx=14)

    def _make_status_bar(self, initial_text: str = "Prêt") -> tk.Label:
        self._label_statut = tk.Label(
            self.win, text=initial_text,
            bg=self.BG, fg=self.FG2, font=("Segoe UI", 9)
        )
        self._label_statut.pack(pady=(0, 10))
        return self._label_statut

    def set_status(self, msg: str, color: str | None = None):
        if self._label_statut is None:
            return
        c = color or self.FG2
        if threading.current_thread() is threading.main_thread():
            self._label_statut.config(text=msg, fg=c)
        else:
            self.win.after(0, lambda m=msg, col=c: self._label_statut.config(text=m, fg=col))

    def build(self):
        raise NotImplementedError

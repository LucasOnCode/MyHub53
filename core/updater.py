import json
import sys
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable


def load_local_version(version_file: Path) -> str:
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def _version_gt(a: str, b: str) -> bool:
    try:
        return tuple(int(x) for x in a.split(".")) > tuple(int(x) for x in b.split("."))
    except Exception:
        return a != b


def check_update(repo: str) -> tuple:
    """Returns (remote_version, download_url) or (None, None) on failure."""
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "MyHub53-Updater"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        version = data["tag_name"].lstrip("v")
        assets = data.get("assets", [])
        dl_url = assets[0]["browser_download_url"] if assets else None
        return version, dl_url
    except Exception:
        return None, None


def has_update(local_version: str, remote_version: str) -> bool:
    return _version_gt(remote_version, local_version)


def download_and_update(download_url: str, on_progress: Callable[[int], None] | None = None):
    if not hasattr(sys, "_MEIPASS"):
        raise RuntimeError("Mise à jour uniquement disponible en version packagée.")

    current_exe = Path(sys.executable)
    tmp = current_exe.with_suffix(".new.exe")

    def _report(block, block_size, total):
        if on_progress and total > 0:
            pct = min(100, int(block * block_size / total * 100))
            on_progress(pct)

    urllib.request.urlretrieve(download_url, tmp, reporthook=_report)

    script = (
        f"Start-Sleep -Seconds 2; "
        f"Move-Item -Force '{tmp}' '{current_exe}'; "
        f"Start-Process '{current_exe}'"
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=0x08000000,
    )
    sys.exit(0)

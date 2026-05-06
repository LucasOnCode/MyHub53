# CLAUDE.md — Guide du projet MonHub

Ce fichier est automatiquement chargé par Claude Code à chaque session.
Il contient tout le contexte nécessaire pour travailler sur ce projet.

---

## Vue d'ensemble

**MonHub** est une application desktop Windows (Python + tkinter) offerte comme cadeau.
C'est un hub qui regroupe plusieurs petits outils utilitaires sous une interface unifiée.
Chaque outil s'ouvre dans sa propre fenêtre `Toplevel` depuis la page principale (hub).

**Contraintes fondamentales :**
- Distribution en **un seul fichier `.exe`** (PyInstaller `--onefile`)
- Mise à jour via **GitHub Releases** — l'utilisatrice clique "Mettre à jour" dans l'app
- Design cohérent entre les outils (palette commune, même style de header)
- Priorité absolue : **sécurité** puis **performance**

---

## Structure du projet

```
MonHub/
├── main.py                    # Hub principal — page d'accueil avec les tiles
├── version.txt                # Version actuelle ex: "1.0.0" — comparée avec GitHub
├── CLAUDE.md                  # Ce fichier
├── MonHub.spec                # Config PyInstaller pour le build
├── icone.ico                  # Icône de l'application
│
├── core/
│   ├── __init__.py
│   ├── base_tool.py           # Classe BaseTool — parente de tous les outils
│   ├── settings.py            # Lecture/écriture settings dans %APPDATA%\MonHub\
│   └── updater.py             # Vérification + téléchargement mises à jour GitHub
│
├── tools/
│   ├── __init__.py
│   ├── registry.py            # TOOLS = liste des ToolCard → génère les tiles du hub
│   └── converter/
│       ├── __init__.py
│       └── ui.py              # MyFileConverter (YouTube → MP3/FLAC/etc.)
│
├── ffmpeg_bin/                # Binaire FFmpeg embarqué (utilisé par le converter)
└── assets/                    # Ressources graphiques futures
```

---

## Ajouter un nouvel outil (procédure exacte)

### Étape 1 — Créer le module de l'outil

Créer `tools/mon_outil/__init__.py` (vide) et `tools/mon_outil/ui.py` :

```python
import tkinter as tk
from core.base_tool import BaseTool

class MonOutilTool(BaseTool):
    def __init__(self, parent):
        super().__init__(parent, name="Mon Outil", accent="#00bcd4",
                         width=600, height=500)

    def build(self):
        # Construire l'UI ici avec self.win, self.BG, self.FG, self.accent, etc.
        self._make_status_bar("Prêt")
        tk.Label(self.win, text="Contenu de l'outil",
                 bg=self.BG, fg=self.FG).pack(pady=20)
```

### Étape 2 — Enregistrer l'outil dans le registry

Dans `tools/registry.py`, ajouter une ligne dans `TOOLS` :

```python
from tools.mon_outil.ui import MonOutilTool

TOOLS = [
    ToolCard(id="converter", name="MyFileConverter", ...),   # existant
    ToolCard(
        id="mon_outil",
        name="Mon Outil",
        description="Ce que fait l'outil en une ligne",
        icon="🔧",
        accent="#00bcd4",
        klass=MonOutilTool,
    ),
]
```

C'est tout. Le hub génère les tiles automatiquement depuis `TOOLS`.

---

## API de BaseTool

```python
class BaseTool:
    # Palette commune (ne pas modifier sans raison)
    BG      = "#0f0f17"   # fond principal
    BG2     = "#1a1a2e"   # fond secondaire (cartes, inputs)
    BG3     = "#222235"   # fond tertiaire (hover, séparateurs)
    FG      = "#f0f0f5"   # texte principal
    FG2     = "#8888aa"   # texte secondaire (labels, hints)
    VERT    = "#22d3a5"   # succès
    ROUGE   = "#ef4444"   # erreur
    JAUNE   = "#f59e0b"   # avertissement

    self.accent    # couleur d'accent propre à l'outil (passée au __init__)
    self.win       # Toplevel tkinter de l'outil
    self.parent    # Fenêtre parente (le hub)

    # Méthodes utilitaires disponibles :
    self._make_status_bar(initial_text)   # crée une barre de statut en bas de self.win
    self.set_status(msg, color)           # met à jour la barre de statut (thread-safe)

    # Méthode à implémenter obligatoirement :
    def build(self):  # construire l'UI dans self.win
        ...
```

---

## Paramètres persistants

Chaque outil a son propre namespace dans `%APPDATA%\MonHub\settings.json` :

```python
import core.settings as settings_store

TOOL_ID = "mon_outil"

# Charger
cfg = settings_store.load(TOOL_ID)
valeur = cfg.get("ma_cle", "valeur_defaut")

# Sauvegarder
settings_store.save(TOOL_ID, {"ma_cle": "nouvelle_valeur"})

# Fichier d'historique dédié à l'outil
hf = settings_store.history_file(TOOL_ID)  # Path vers %APPDATA%\MonHub\mon_outil_history.json
```

---

## Système de mise à jour

### Configuration (à faire une fois)
Dans `main.py`, définir :
```python
GITHUB_REPO = "ton_username/ton_repo"   # repo GitHub du projet
```

### Workflow de release
1. Modifier le code
2. Changer `version.txt` → ex: `1.1.0`
3. Builder : `pyinstaller MonHub.spec`
4. Sur GitHub : créer une Release avec le tag `v1.1.0`, uploader `dist/MonHub.exe`

### Ce qui se passe côté utilisatrice
- Au démarrage, l'app vérifie silencieusement GitHub (timeout 5s, ne bloque pas l'UI)
- Si nouvelle version : badge "▲ vX.X dispo" dans le header, bouton "Installer"
- Sur clic : télécharge le `.exe`, le place à côté, lance un script PowerShell qui attend
  la fermeture de l'app, remplace l'ancien `.exe`, relance

### En mode développement
La mise à jour automatique est désactivée (fonctionne uniquement avec le `.exe` packagé).

---

## Build PyInstaller

```bash
# Activer le venv d'abord
.\venv\Scripts\activate

# Builder
pyinstaller MonHub.spec

# L'exe est dans dist\MonHub.exe
```

Le `.spec` inclut automatiquement : `icone.ico`, `ffmpeg_bin/`, `version.txt`.

---

## Conventions de code

- Pas de commentaires sauf si le WHY est non-évident
- Tous les updates UI depuis un thread → `self.win.after(0, lambda: ...)`
- Validation à la frontière système uniquement (inputs utilisateur, URLs, chemins)
- Chaque outil est une classe autonome — pas de globals partagés entre outils
- Les settings sont namespaced par `TOOL_ID` pour éviter les collisions
- `windowsfilenames: True` dans tous les yt-dlp opts (path traversal prevention)
- Chemins toujours via `Path(...).resolve()` avant usage dans outtmpl

---

## Outils existants

| ID | Classe | Description |
|---|---|---|
| `converter` | `ConverterTool` | YouTube → MP3/FLAC/M4A/WAV/OGG, parallélisme configurable, tags ID3, historique |

---

## Dépendances Python

```
yt-dlp
tkinter (stdlib)
```
Pas de dépendances externes supplémentaires — tout ce qui sort du stdlib est justifié.
`packaging` est volontairement évité (comparaison de versions maison dans `updater.py`).

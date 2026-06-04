# CLAUDE.md — Guide du projet MyHub53

Ce fichier est automatiquement chargé par Claude Code à chaque session.

---

## Vue d'ensemble

**MyHub53** est une application desktop Windows en **PySide6** (Python), offerte comme cadeau à Romy.
C'est un hub qui regroupe plusieurs outils utilitaires sous une interface unifiée et animée.
Chaque outil s'ouvre dans sa propre fenêtre frameless depuis la page principale.

**Version actuelle : 1.3.0** — publiée sur GitHub Releases.

**Contraintes fondamentales :**
- Distribution en **un seul fichier `.exe`** (PyInstaller onefile via `MyHub53.spec`)
- Mise à jour via **GitHub Releases** (`LucasOnCode/MyHub53`) — badge dans le header
- Design cohérent : palette `core/theme.py`, même structure de fenêtre pour chaque outil
- Priorité : **sécurité** puis **performance**

---

## Structure du projet

```
MyHub53/
├── main.py                    # MainWindow (QWidget frameless) — hub principal
├── version.txt                # "1.2.0" — comparée avec GitHub au démarrage
├── CLAUDE.md                  # Ce fichier
├── MyHub53.spec               # Config PyInstaller (onefile)
├── icone.ico
│
├── core/
│   ├── theme.py               # Tokens couleurs, fonts, QSS generators
│   ├── hub_widgets.py         # BrandMark, HeaderBar, Hero, CategoryTile,
│   │                          # RecentTile, EmptyTile, SettingsDialog,
│   │                          # CategoryBrowserDialog, NameDialog, SectionHead
│   ├── effects.py             # ParticleLayer — overlay animé dans le hub
│   ├── aquatic_bg.py          # AquaticBg — fond aquatique animé (outils "aquatic")
│   ├── atmos.py               # AtmosBg — fond sombre statique (hub + outils "plain")
│   ├── base_tool.py           # BaseTool(QWidget) — parent de tous les outils
│   ├── win_chrome.py          # Aero Snap + WS_THICKFRAME via ctypes
│   ├── settings.py            # %APPDATA%\MyHub53\settings.json (merge par namespace)
│   └── updater.py             # check_update / download_and_update
│
├── tools/
│   ├── registry.py            # CATEGORIES, TOOLS (ToolCard), tools_in_category()
│   └── converter/
│       └── ui.py              # ConverterTool — YouTube → MP3/FLAC/M4A/WAV/OGG
│
├── ffmpeg_bin/                # FFmpeg embarqué (requis par yt-dlp)
└── assets/fonts/              # Quicksand, Fraunces, JetBrains Mono (TTF)
```

---

## Architecture du hub (main.py)

`MainWindow(QWidget)` est frameless. Ses enfants directs forment une pile :

1. `AtmosBg` — fond statique (3 blobs radial gradient sur fond sombre)
2. `ParticleLayer` — overlay particules flottantes (animé, mouse-transparent)
3. `content` (QWidget) — header + scroll area avec hero, catégories, recents

**Système de pause des animations :**
```python
self._pause_reasons: set[str]   # vide = animé, non-vide = pausé
# Raisons : "minimized", "hidden", "tool_open"
# Visibilité contrôlée par : self.particles.setVisible(self._particles_enabled)
```

**Settings hub** (`HUB_SETTINGS_ID = "hub"`) :
```json
{
  "user_name": "Romy",
  "particles_enabled": true,
  "recent_tools": { "converter": "2026-05-07T14:32:10" }
}
```

**Recents** : triés par `last_used` décroissant, timestamp ISO enregistré à chaque ouverture.

**Layout responsive** : la grille de catégories passe de 4 → 3 → 2 colonnes selon la largeur viewport (seuils `CAT_BREAK_3=920`, `CAT_BREAK_2=660`).

---

## Ajouter un nouvel outil

### Étape 1 — Créer le module

`tools/mon_outil/__init__.py` (vide) et `tools/mon_outil/ui.py` :

```python
from PySide6.QtWidgets import QLabel, QVBoxLayout
from core.base_tool import BaseTool
from core import theme

class MonOutilTool(BaseTool):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            name="Mon Outil",
            accent=theme.TURQUOISE,
            univers="plain",       # "aquatic" (animé) ou "plain" (statique)
            width=700, height=600,
        )

    def build(self):
        # Ajouter des widgets à self.body_layout (QVBoxLayout)
        lbl = QLabel("Contenu de l'outil")
        lbl.setFont(theme.font("body", 14))
        lbl.setStyleSheet(f"color: {theme.FG}; background: transparent;")
        self.body_layout.addWidget(lbl)
        self._make_status_bar("Prêt")
```

### Étape 2 — Enregistrer dans le registry

Dans `tools/registry.py`, ajouter dans `_load_tools()` :

```python
ToolCard(
    id="mon_outil",
    name="Mon Outil",
    description="Ce que fait l'outil en une ligne",
    icon="🔧",
    accent=theme.TURQUOISE,
    klass=MonOutilTool,
    category="outils",      # id d'une Category existante
    univers="plain",
),
```

---

## API de BaseTool

```python
class BaseTool(QWidget):
    # Paramètres du constructeur
    name: str           # titre affiché dans la titlebar
    accent: str         # hex couleur d'accent (barre colorée, bordures hover)
    univers: str        # "aquatic" → AquaticBg animé | "plain" → AtmosBg statique
    width, height       # taille initiale
    min_w, min_h        # taille minimum

    # Attributs disponibles dans build()
    self.body_layout    # QVBoxLayout — ajouter les widgets ici
    self.accent         # couleur d'accent
    self.tool_name      # nom de l'outil

    # Méthodes utilitaires
    self._make_status_bar("Prêt")       # crée une barre de statut en bas
    self.set_status(msg, color)         # thread-safe via Signal (color = hex ou None)
```

**Thread-safety** : tout update UI depuis un worker thread → `self.mon_signal.emit(valeur)` (Qt queue automatiquement vers le thread UI). Ne jamais appeler `widget.setText()` depuis un thread.

---

## Tokens de thème (core/theme.py)

```python
# Couleurs principales
INK_DEEPEST  = "#0a0d1f"   # fond le plus sombre
INK_DEEP     = "#161a3a"   # fond cartes / dialogs
INK_MID      = "#2e3a78"
TURQUOISE    = "#5fc8d8"   # accent principal
FRAMBOISE    = "#e84d6f"   # accent chaud
IRIS         = "#9b5edb"   # accent violet
GOLD         = "#d4b378"   # accent doré
FG           = "#f5f3ee"   # texte principal
FG_MUTED     = "#a5b0d0"   # texte secondaire
SUCCESS      = "#22d3a5"
ERROR        = "#ef4444"
WARNING      = "#f59e0b"

# Fonctions
theme.font("body"|"display"|"mono", size, weight, italic, letter_spacing)
theme.rgba(hex_color, alpha_0_to_1)   # → "rgba(r, g, b, a)"

# QSS generators
theme.qss_button_primary()
theme.qss_button_ghost()
theme.qss_input()
theme.qss_pill(active=bool)
theme.qss_close_btn()
```

---

## Paramètres persistants

```python
import core.settings as settings_store

TOOL_ID = "mon_outil"

cfg = settings_store.load(TOOL_ID)             # dict (merge avec existant)
val = cfg.get("ma_cle", "defaut")
settings_store.save(TOOL_ID, {"ma_cle": val}) # merge — ne supprime pas les autres clés
hf  = settings_store.history_file(TOOL_ID)    # Path vers mon_outil_history.json
```

---

## Univers (fonds de fenêtre)

| `univers=` | Fond | Animation |
|---|---|---|
| `"aquatic"` | Gradient bleu-nuit + 3 blobs caustics | Oui (bulles montantes, 30fps) |
| `"plain"` | AtmosBg — 3 blobs radial gradient | Non (statique) |
| `"parchment"` | À venir | — |
| `"velvet"` | À venir | — |

---

## Système de mise à jour

- `GITHUB_REPO = "LucasOnCode/MyHub53"` dans `main.py`
- Vérification silencieuse 3s après démarrage (thread daemon)
- Badge `▲ vX.X disponible` dans le header si mise à jour dispo
- Téléchargement → script PowerShell remplace l'exe et relance

### Workflow de release
```
1. Modifier le code
2. Bumper version.txt  (ex: 1.3.0)
3. pyinstaller MyHub53.spec --noconfirm --clean
4. git add ... && git commit -m "v1.3.0 — ..."
5. git tag v1.3.0 && git push origin master --tags
6. GitHub → Releases → New release → tag v1.3.0 → upload dist/MyHub53.exe
```

---

## Build PyInstaller

```powershell
.\venv\Scripts\activate
pyinstaller MyHub53.spec --noconfirm --clean
# → dist\MyHub53.exe (~120 MB)
```

Le `.spec` inclut : `icone.ico`, `ffmpeg_bin/`, `version.txt`, `assets/fonts/`.
Hidden imports : `yt_dlp`, `yt_dlp.postprocessor`, `yt_dlp.extractor`, `tools.converter.ui`.

---

## Conventions de code

- Pas de commentaires sauf WHY non-évident
- Updates UI depuis thread → Signal/Slot (jamais `widget.method()` direct depuis thread)
- Validation uniquement aux frontières système (inputs user, URLs, chemins)
- Chaque outil est autonome — pas de globals partagés entre outils
- Settings namespaced par `TOOL_ID`
- `windowsfilenames: True` dans tous les yt-dlp opts (sécurité path traversal)
- Chemins via `Path(...).resolve()` avant usage dans outtmpl

---

## Outils existants

| ID | Classe | Univers | Description |
|---|---|---|---|
| `converter` | `ConverterTool` | `plain` | YouTube → MP3/FLAC/M4A/WAV/OGG, parallélisme 1-5, tags ID3, historique |

## Catégories définies

Musique, Cinéma, Cuisine, Jeu vidéo, Peinture, Crochet, Outils, Voir tout (is_all).

## Outils futurs envisagés

- MyCarnetRecettes (univers parchment, catégorie cuisine)
- MyCinéthèque (univers velvet, catégorie cinéma)
- MyPatronsCrochet (catégorie crochet)
- MyLyrics (catégorie musique)

---

## Dépendances Python

```
PySide6==6.11.0
yt-dlp
```
`packaging` volontairement absent (comparaison de versions maison dans `updater.py`).

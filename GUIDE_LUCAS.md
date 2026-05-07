# Guide MyHub53 — Référence personnelle

## Lancer l'app en développement

```powershell
cd D:\LOGICIELS\MyFileConverter
.\venv\Scripts\activate
python main.py
```

---

## Publier une mise à jour

### 1. Modifier le code
Fais tes changements dans les fichiers Python.

### 2. Changer le numéro de version
Ouvrir `version.txt` et incrémenter :
- Nouveau petit fix → `1.0.1`
- Nouveau fonctionnalité → `1.1.0`
- Grosse refonte → `2.0.0`

### 3. Builder l'exe
```powershell
cd D:\LOGICIELS\MyFileConverter
.\venv\Scripts\activate
pyinstaller MyHub53.spec
```
L'exe est généré dans `dist\MyHub53.exe`.

### 4. Push le code sur GitHub
```powershell
git add .
git commit -m "description du changement"
git push
```

### 5. Créer une Release GitHub
1. Aller sur https://github.com/LucasOnCode/MyHub53/releases/new
2. Champ "Choose a tag" → taper `v1.1.0` (adapter le numéro) → "Create new tag"
3. Title → `MyHub53 v1.1.0`
4. Uploader `dist\MyHub53.exe` dans la zone "Attach binaries"
5. Cliquer **Publish release**

L'app de ta copine affichera automatiquement "▲ v1.1.0 dispo" au prochain démarrage.

---

## Ajouter un nouvel outil

### 1. Créer les fichiers de l'outil
```
tools/
└── mon_outil/
    ├── __init__.py   (vide)
    └── ui.py
```

Contenu minimal de `ui.py` :
```python
import tkinter as tk
from core.base_tool import BaseTool

class MonOutilTool(BaseTool):
    def __init__(self, parent):
        super().__init__(parent, name="Mon Outil", accent="#00bcd4",
                         width=600, height=500)

    def build(self):
        self._make_status_bar("Prêt")
        tk.Label(self.win, text="Contenu ici",
                 bg=self.BG, fg=self.FG).pack(pady=20)
```

### 2. Enregistrer dans le registry
Dans `tools/registry.py`, ajouter dans la liste `TOOLS` :
```python
from tools.mon_outil.ui import MonOutilTool

ToolCard(
    id="mon_outil",
    name="Mon Outil",
    description="Description courte",
    icon="🔧",
    accent="#00bcd4",
    klass=MonOutilTool,
),
```

### 3. Ajouter dans le .spec si nécessaire
Si l'outil a des assets (images, binaires...), les ajouter dans `MonHub.spec` :
```python
datas=[
    ('icone.ico', '.'),
    ('ffmpeg_bin', 'ffmpeg_bin'),
    ('version.txt', '.'),
    ('mon_asset', 'mon_asset'),   # ajouter ici
],
```

---

## Couleurs disponibles (palette commune)

| Variable | Valeur | Usage |
|---|---|---|
| `self.BG` | `#0f0f17` | Fond principal |
| `self.BG2` | `#1a1a2e` | Cartes, inputs |
| `self.BG3` | `#222235` | Hover, séparateurs |
| `self.FG` | `#f0f0f5` | Texte principal |
| `self.FG2` | `#8888aa` | Texte secondaire |
| `self.VERT` | `#22d3a5` | Succès |
| `self.ROUGE` | `#ef4444` | Erreur |
| `self.JAUNE` | `#f59e0b` | Avertissement |
| `self.accent` | variable | Couleur propre à l'outil |

---

## Sauvegarder des paramètres dans un outil

```python
import core.settings as settings_store

TOOL_ID = "mon_outil"

# Charger
cfg = settings_store.load(TOOL_ID)
valeur = cfg.get("ma_cle", "valeur_par_defaut")

# Sauvegarder
settings_store.save(TOOL_ID, {"ma_cle": nouvelle_valeur})
```

Les settings sont stockés dans `%APPDATA%\MyHub53\settings.json`.

---

## Fichiers importants

| Fichier | Rôle |
|---|---|
| `main.py` | Hub principal — page d'accueil |
| `version.txt` | Numéro de version actuel |
| `tools/registry.py` | Liste des outils (tiles) |
| `core/base_tool.py` | Classe parente de tous les outils |
| `core/settings.py` | Lecture/écriture des paramètres |
| `core/updater.py` | Système de mise à jour GitHub |
| `MonHub.spec` | Config PyInstaller pour le build |

---

## En cas de problème

**L'exe ne se lance pas** → Vérifier que `ffmpeg_bin/` est bien dans le dossier source avant de builder.

**La mise à jour ne se détecte pas** → Vérifier que le tag GitHub commence bien par `v` (ex: `v1.1.0`) et que `version.txt` est bien à jour avant de builder.

**Un outil n'apparaît pas** → Vérifier que la classe est bien importée et ajoutée dans `TOOLS` dans `tools/registry.py`.

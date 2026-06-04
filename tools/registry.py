from dataclasses import dataclass, field
from typing import Literal, Optional, Type, TYPE_CHECKING

from core import theme

if TYPE_CHECKING:
    from core.base_tool import BaseTool


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    icon: str
    c1: str   # gradient stop 1 (hex)
    c2: str   # gradient stop 2 (hex)
    is_all: bool = False


@dataclass
class ToolCard:
    id:          str
    name:        str
    description: str
    icon:        str
    accent:      str
    klass:       "Type[BaseTool]"
    category:    str = "outils"
    univers:     Literal["aquatic", "plain", "parchment", "velvet"] = "aquatic"
    glow:        str = ""
    last_used:   Optional[str] = None


CATEGORIES: list[Category] = [
    Category("musique",  "Musique",   "♪", theme.TURQUOISE,      theme.IRIS),
    Category("cinema",   "Cinéma",    "▶", theme.FRAMBOISE,      theme.IRIS),
    Category("cuisine",  "Cuisine",   "✦", theme.FRAMBOISE_SOFT, theme.GOLD),
    Category("jeux",     "Jeu vidéo", "◆", theme.IRIS,           theme.TURQUOISE_DEEP),
    Category("peinture", "Peinture",  "❋", theme.TURQUOISE,      theme.FRAMBOISE),
    Category("crochet",  "Crochet",   "❀", theme.FRAMBOISE_SOFT, theme.IRIS_SOFT),
    Category("outils",   "Outils",    "✜", theme.GOLD,           theme.TURQUOISE_DEEP),
    Category("all",      "Voir tout", "✧", theme.IRIS,           theme.TURQUOISE, is_all=True),
]


def _load_tools() -> list[ToolCard]:
    from tools.converter.ui import ConverterTool

    return [
        ToolCard(
            id="converter",
            name="MyFileConverter",
            description="YouTube → MP3, FLAC, M4A",
            icon="🎵",
            accent=theme.TURQUOISE,
            klass=ConverterTool,
            category="musique",
            univers="plain",
            glow=theme.rgba(theme.TURQUOISE, 0.45),
            last_used=None,
        ),
    ]


TOOLS: list[ToolCard] = _load_tools()


def tools_in_category(cat_id: Optional[str]) -> list[ToolCard]:
    if cat_id is None or cat_id == "all":
        return list(TOOLS)
    return [t for t in TOOLS if t.category == cat_id]


def category_count(cat: Category) -> int:
    if cat.is_all:
        return len(TOOLS)
    return sum(1 for t in TOOLS if t.category == cat.id)

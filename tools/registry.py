from dataclasses import dataclass
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from core.base_tool import BaseTool


@dataclass
class ToolCard:
    id:          str
    name:        str
    description: str
    icon:        str
    accent:      str
    klass:       "Type[BaseTool]"


def _load_tools() -> list[ToolCard]:
    from tools.converter.ui import ConverterTool

    return [
        ToolCard(
            id="converter",
            name="MyFileConverter",
            description="YouTube → MP3 / FLAC / M4A",
            icon="🎵",
            accent="#e84393",
            klass=ConverterTool,
        ),
        # Pour ajouter un outil :
        # from tools.mon_outil.ui import MonOutilTool
        # ToolCard(id="mon_outil", name="...", description="...",
        #          icon="🔧", accent="#00bcd4", klass=MonOutilTool),
    ]


TOOLS: list[ToolCard] = _load_tools()

"""Links to WRFrontiersDB-Data's texture files (object icons).

Data stores each texture at `textures<texture path>.png`, where the texture path is
what objects carry (`inventory_icon_path`: `/WRFrontiers/Content/.../T_Module_ChassisAres`).
Links point at that file in the Data repo itself, pinned to the commit the bot reads, so
an icon always matches the data it answers from and never depends on a Site deploy.
"""

from pathlib import Path

DEFAULT_DATA_RAW_URL = 'https://raw.githubusercontent.com/Surxe/WRFrontiersDB-Data'


class TextureLinks:
    def __init__(self, raw_url: str, commit: str | None, textures_dir: Path):
        self.raw_url = raw_url.rstrip('/')
        self.commit = commit
        self.textures_dir = textures_dir

    def url(self, texture_path: str | None) -> str | None:
        """URL of a texture's PNG, or None without a path, a known commit, or the file in Data."""
        if not texture_path or not self.commit:
            return None
        relative = texture_path.lstrip('/') + '.png'
        if not (self.textures_dir / relative).is_file():
            return None
        return f'{self.raw_url}/{self.commit}/textures/{relative}'

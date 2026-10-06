"""Read-only access to a local WRFrontiersDB-Data clone."""

import json
from pathlib import Path


class DataRepo:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.current_dir = self.data_dir / 'current'
        self.version_file = self.current_dir / 'version.txt'
        self.objects_dir = self.current_dir / 'Objects'
        self.slug_map_file = self.data_dir / 'index' / 'slug_map.json'
        self.nicknames_file = self.data_dir / 'index' / 'nicknames.json'
        self.aliases_file = self.data_dir / 'index' / 'aliases.json'

    def read_version(self) -> str:
        return self.version_file.read_text(encoding='utf-8').strip()

    def read_objects(self, object_type_name: str) -> dict[str, dict]:
        """All objects of one type, id -> object."""
        objects_file = self.objects_dir / f'{object_type_name}.json'
        with objects_file.open(encoding='utf-8') as f:
            return json.load(f)

    def read_slug_map(self) -> dict[str, str]:
        """Object id -> slug of its Site page; only objects with a page are listed."""
        with self.slug_map_file.open(encoding='utf-8') as f:
            return json.load(f)

    def read_nicknames(self) -> dict[str, list[str]]:
        """Object id -> short names it is known by (a pilot's first name); for matching only."""
        with self.nicknames_file.open(encoding='utf-8') as f:
            return json.load(f)

    def read_aliases(self) -> dict[str, list[str]]:
        """Object id -> full alternative names (`Wyrm Chassis`); for matching and display."""
        with self.aliases_file.open(encoding='utf-8') as f:
            return json.load(f)

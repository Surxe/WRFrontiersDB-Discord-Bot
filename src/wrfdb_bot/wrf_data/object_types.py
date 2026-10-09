"""The WRFrontiersDB-Data object types the bot knows, and how to read each one."""

from collections.abc import Sequence
from dataclasses import dataclass

from .localization import default_string


@dataclass(frozen=True)
class ObjectType:
    name: str
    """Data object class; also the file name `Objects/<name>.json`."""
    label: str
    """Human name, matching the Site's wording."""
    site_route: str
    """Site page directory: an object's page is `/<site_route>/<slug>/`."""
    prefixes: tuple[str, ...]
    """Type prefixes users may write (`[[talent:vanguard]]`). Normalized when matched."""


# In priority order: when one name matches several types, the earlier type wins.
OBJECT_TYPES: tuple[ObjectType, ...] = (
    ObjectType('VirtualBot', 'Robot', 'robots', ('robot', 'bot')),
    ObjectType('Pilot', 'Pilot', 'pilots', ('pilot',)),
    ObjectType('Module', 'Module', 'modules', ('module', 'mod')),
    ObjectType('PilotTalent', 'Pilot Talent', 'pilot_talents', ('talent', 'pilot talent')),
    ObjectType('CharacterClass', 'Character Class', 'character_classes', ('character class', 'robot class')),
    ObjectType('PilotClass', 'Pilot Class', 'pilot_classes', ('pilot class',)),
    ObjectType('Faction', 'Faction', 'factions', ('faction',)),
    ObjectType('PilotPersonality', 'Pilot Personality', 'pilot_personalities', ('personality', 'pilot personality')),
    ObjectType('PilotTalentType', 'Pilot Talent Type', 'pilot_talent_types', ('talent type', 'pilot talent type')),
    ObjectType('ModuleGroup', 'Module Group', 'module_groups', ('module group', 'group')),
    ObjectType('ModuleCategory', 'Module Category', 'module_categories', ('module category', 'category')),
    ObjectType('Currency', 'Currency', 'currencies', ('currency',)),
)

OBJECT_TYPES_BY_NAME: dict[str, ObjectType] = {t.name: t for t in OBJECT_TYPES}


def is_published(object_type: ObjectType, obj: dict) -> bool:
    """Whether the Site publishes this object (and so the bot should index it)."""
    if object_type.name == 'Module':
        # Same rule as the Site's build-slugs.ts: a missing status means not ready.
        return obj.get('production_status') == 'Ready'
    return True


def object_name(object_type: ObjectType, obj: dict) -> str:
    """English display name of an object."""
    if object_type.name == 'Pilot':
        first_name = default_string(obj.get('first_name'))
        last_name = default_string(obj.get('last_name') or obj.get('second_name'))
        return f'{first_name} {last_name}'.strip()
    return default_string(obj.get('name'))


def display_name(name: str, aliases: Sequence[str]) -> str:
    """Name to show for an object: its first alias (Data's `index/aliases.json`) when it has
    one, since the plain name isn't distinctive there (robot parts), else `name`."""
    return aliases[0] if aliases else name


def object_description(object_type: ObjectType, obj: dict) -> str:
    """English description (pilot bio for pilots), or "" if none."""
    if object_type.name == 'Pilot':
        return default_string(obj.get('bio'))
    return default_string(obj.get('description'))


def ref_to_id(ref: str) -> str:
    """`OBJID_VirtualBot::alpha` -> `alpha`."""
    return ref.split('::', 1)[-1]

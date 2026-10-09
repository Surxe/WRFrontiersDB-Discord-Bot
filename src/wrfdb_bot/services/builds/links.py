"""Reading the Site's `/models?a=<code>&b=<code>` links. Free of Discord, so it stays testable."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from wrfdb_bot.wrf_data.build_codes import Build, BuildCodes
from wrfdb_bot.wrf_data.object_types import OBJECT_TYPES_BY_NAME, display_name, object_name
from wrfdb_bot.wrf_data.store import DataSnapshot

MAX_LINKS_PER_MESSAGE = 5

SLOT_LABELS = {
    'chassis': 'Chassis',
    'torso': 'Torso',
    'Shoulder_L': 'Left shoulder',
    'Shoulder_L.Shoulder_Weapon_0': 'Left weapon 1',
    'Shoulder_L.Shoulder_Weapon_1': 'Left weapon 2',
    'Shoulder_R': 'Right shoulder',
    'Shoulder_R.Shoulder_Weapon_0': 'Right weapon 1',
    'Shoulder_R.Shoulder_Weapon_1': 'Right weapon 2',
    'Torso_Weapon_0': 'Torso weapon',
    'Ability': 'Supply gear',
    'UltAbility': 'Cycle gear',
}
"""Labels for the Site's slot keys; any other key is shown as it is."""

MODULE = OBJECT_TYPES_BY_NAME['Module']


@dataclass(frozen=True)
class Part:
    slot: str
    """Label of the slot (`Left shoulder`)."""
    name: str
    url: str | None


@dataclass(frozen=True)
class BuildLink:
    """One `/models` link: its builds' parts, or why they couldn't be read."""

    builds: tuple[tuple[Part, ...], ...] = ()
    """Build A's parts, then build B's when the link compares two builds."""
    too_new: bool = False
    """A code uses parts newer than the bot's data."""
    invalid: bool = False
    """A code isn't a build code."""
    codes: tuple[str, ...] = ()
    """The link's codes, A first."""


def find_codes(content: str, site_url: str) -> list[tuple[str, str | None]]:
    """(a code, b code or None) for each `<site>/models?...a=...` link, in order."""
    host = urlsplit(site_url).netloc
    pattern = re.compile(rf'https?://(?:www\.)?{re.escape(host)}/models/?\?[^\s<>]+')
    found = []
    for match in pattern.finditer(content):
        query = parse_qs(urlsplit(match.group(0)).query)
        a = query.get('a', [None])[0]
        if a:
            found.append((a, query.get('b', [None])[0]))
        if len(found) == MAX_LINKS_PER_MESSAGE:
            break
    return found


def read_link(snapshot: DataSnapshot, codes: BuildCodes, a: str, b: str | None) -> BuildLink:
    all_codes = (a,) if b is None else (a, b)
    try:
        builds = tuple(codes.decode(code) for code in all_codes)
    except codes.TooNew:
        return BuildLink(too_new=True, codes=all_codes)
    except codes.Error:
        return BuildLink(invalid=True, codes=all_codes)
    return BuildLink(builds=tuple(parts(snapshot, build) for build in builds), codes=all_codes)


def parts(snapshot: DataSnapshot, build: Build) -> tuple[Part, ...]:
    """The build's parts in slot order, named like lookups name them."""
    modules = snapshot.objects.get(MODULE.name, {})
    result = []
    for key, module_id in build.items():
        name = object_name(MODULE, modules.get(module_id, {})) or module_id
        name = display_name(name, snapshot.names.aliases.get(module_id, ()))
        result.append(Part(SLOT_LABELS.get(key, key), name, snapshot.site_links.page_url(MODULE, module_id)))
    return tuple(result)

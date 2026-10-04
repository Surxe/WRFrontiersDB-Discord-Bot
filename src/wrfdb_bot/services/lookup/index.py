"""The lookup index: resolves user queries to WRF objects by English name."""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from wrfdb_bot.wrf_data.object_types import (
    OBJECT_TYPES,
    OBJECT_TYPES_BY_NAME,
    ObjectType,
    is_published,
    object_description,
    object_name,
    ref_to_id,
)
from wrfdb_bot.wrf_data.store import DataSnapshot

from .lookup_key import to_lookup_key
from .query_parser import split_type_prefix

FUZZY_MATCH_MIN_SCORE = 85
"""A fuzzy result at or above this score is used as the answer..."""
FUZZY_MATCH_MIN_LEAD = 3
"""...if it also beats the runner-up by this much. Partial matches tie often
("gun" scores the same against Railgun and Gun Nut); a tie gets suggestions instead."""
SUGGESTION_MIN_SCORE = 70
"""Below FUZZY_MATCH_MIN_SCORE, results at or above this are offered as suggestions."""
MAX_SUGGESTIONS = 3
MAX_DESCRIPTION_LENGTH = 300

_ROBOT_PARTS = ('Chassis', 'Torso', 'Shoulder')
_SHOULDER_SIDES = {'L': 'Left', 'R': 'Right'}
_RICH_TEXT_TAG = re.compile(r'<[^>]*>')


@dataclass
class LookupEntry:
    object_type: ObjectType
    object_id: str
    name: str
    url: str | None
    description: str
    aliases: tuple[str, ...] = ()
    """Other names that reach this entry (e.g. `Alpha Chassis` for a robot part)."""
    nicknames: tuple[str, ...] = ()
    """Short names from Data's `index/nicknames.json` (`Marcus` for Marcus Shedd). They
    reach the entry only when no object has that exact name, and are never fuzzy-matched."""
    hint: str = ''
    """Shortest query that resolves to exactly this entry; set by the index."""
    priority: int = field(default=0, repr=False)

    @property
    def display_name(self) -> str:
        """Name to show: the first alias when the plain name isn't distinctive (robot parts)."""
        return self.aliases[0] if self.aliases else self.name


@dataclass(frozen=True)
class LookupResult:
    query: str
    entry: LookupEntry | None
    is_fuzzy: bool = False
    other_matches: tuple[LookupEntry, ...] = ()
    """Other objects with the same name (lower priority types / robot parts)."""
    suggestions: tuple[LookupEntry, ...] = ()
    """Near misses, when there was no answer."""


class LookupIndex:
    def __init__(self, entries: list[LookupEntry]):
        self.entries = entries
        self._entries_by_key: dict[str, list[LookupEntry]] = defaultdict(list)
        self._entries_by_nickname_key: dict[str, list[LookupEntry]] = defaultdict(list)
        for entry in sorted(entries, key=lambda e: (e.priority, e.object_id)):
            for text in (entry.name, *entry.aliases):
                key = to_lookup_key(text)
                if key and entry not in self._entries_by_key[key]:
                    self._entries_by_key[key].append(entry)
            for text in entry.nicknames:
                key = to_lookup_key(text)
                if key and entry not in self._entries_by_nickname_key[key]:
                    self._entries_by_nickname_key[key].append(entry)
        self._types_by_prefix_key = {
            to_lookup_key(prefix): object_type for object_type in OBJECT_TYPES for prefix in object_type.prefixes
        }
        # Fuzzy choices (lookup key -> spaced text for scoring), per type filter.
        self._fuzzy_choices: dict[str | None, dict[str, str]] = defaultdict(dict)
        for key, key_entries in self._entries_by_key.items():
            spaced = key.replace('-', ' ')
            self._fuzzy_choices[None][key] = spaced
            for entry in key_entries:
                self._fuzzy_choices[entry.object_type.name][key] = spaced
        for entry in entries:
            entry.hint = self._find_hint(entry)

    @classmethod
    def from_snapshot(cls, snapshot: DataSnapshot) -> 'LookupIndex':
        return cls(_build_entries(snapshot))

    def resolve(self, query: str) -> LookupResult:
        object_type, name = self._split_known_prefix(query)
        key = to_lookup_key(name)
        matches = self._exact_matches(key, object_type) or self._nickname_matches(key, object_type)
        if matches:
            return LookupResult(query, matches[0], other_matches=tuple(matches[1:]))

        scored = self._fuzzy(name, object_type, limit=MAX_SUGGESTIONS + 1)
        if _is_clear_fuzzy_match(scored):
            best_matches = self._exact_matches(scored[0][0], object_type)
            return LookupResult(query, best_matches[0], is_fuzzy=True, other_matches=tuple(best_matches[1:]))
        suggestions = [
            self._exact_matches(key, object_type)[0] for key, score in scored if score >= SUGGESTION_MIN_SCORE
        ]
        return LookupResult(query, None, suggestions=tuple(suggestions[:MAX_SUGGESTIONS]))

    def autocomplete(self, text: str, limit: int = 25) -> list[LookupEntry]:
        """Entries for a partly typed query, best first."""
        object_type, name = self._split_known_prefix(text)
        key = to_lookup_key(name)
        if not key:
            return []
        # A nickname leads only where resolve() would answer with it.
        results = [] if self._exact_matches(key, object_type) else self._nickname_matches(key, object_type)
        for key, _score in self._fuzzy(name, object_type, limit=limit):
            for entry in self._exact_matches(key, object_type):
                if entry not in results:
                    results.append(entry)
        return results[:limit]

    def _split_known_prefix(self, query: str) -> tuple[ObjectType | None, str]:
        prefix, name = split_type_prefix(query)
        if prefix is not None:
            object_type = self._types_by_prefix_key.get(to_lookup_key(prefix))
            if object_type is not None:
                return object_type, name
        # No prefix, or not a type name: the colon is part of the name.
        return None, query.strip()

    def _exact_matches(self, key: str, object_type: ObjectType | None) -> list[LookupEntry]:
        matches = self._entries_by_key.get(key, [])
        if object_type is not None:
            matches = [e for e in matches if e.object_type is object_type]
        return matches

    def _nickname_matches(self, key: str, object_type: ObjectType | None) -> list[LookupEntry]:
        matches = self._entries_by_nickname_key.get(key, [])
        return [e for e in matches if object_type is None or e.object_type is object_type]

    def _fuzzy(self, name: str, object_type: ObjectType | None, limit: int) -> list[tuple[str, float]]:
        """(lookup key, score) pairs, best first."""
        choices = self._fuzzy_choices[object_type.name if object_type else None]
        query = to_lookup_key(name).replace('-', ' ')
        if not query or not choices:
            return []
        return [
            (key, score) for _choice, score, key in process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)
        ]

    def _find_hint(self, entry: LookupEntry) -> str:
        names = (entry.name, *entry.aliases)
        prefix = entry.object_type.prefixes[0]
        candidates = [*names, *(f'{prefix}:{n}' for n in names)]
        for candidate in candidates:
            object_type, name = self._split_known_prefix(candidate)
            matches = self._exact_matches(to_lookup_key(name), object_type)
            if matches and matches[0] is entry:
                return candidate
        return f'{prefix}:{entry.name}'


def _is_clear_fuzzy_match(scored: list[tuple[str, float]]) -> bool:
    if not scored or scored[0][1] < FUZZY_MATCH_MIN_SCORE:
        return False
    return len(scored) == 1 or scored[0][1] - scored[1][1] >= FUZZY_MATCH_MIN_LEAD


def _build_entries(snapshot: DataSnapshot) -> list[LookupEntry]:
    module_groups = snapshot.objects.get('ModuleGroup', {})
    entries: list[LookupEntry] = []
    for priority, object_type in enumerate(OBJECT_TYPES):
        for object_id, obj in snapshot.objects.get(object_type.name, {}).items():
            if not is_published(object_type, obj):
                continue
            name = object_name(object_type, obj)
            if not to_lookup_key(name):
                continue
            entries.append(
                LookupEntry(
                    object_type=object_type,
                    object_id=object_id,
                    name=name,
                    url=snapshot.site_links.page_url(object_type, object_id),
                    description=_entry_description(snapshot, object_type, object_id, obj),
                    aliases=_robot_part_aliases(object_type, obj, name, module_groups),
                    nicknames=tuple(snapshot.nicknames.get(object_id, ())),
                    priority=priority,
                )
            )
    return entries


def _robot_part_aliases(object_type: ObjectType, obj: dict, name: str, module_groups: dict) -> tuple[str, ...]:
    """`Alpha Chassis`, `Alpha Shoulder Left`, ... for modules named after their robot."""
    if object_type is not OBJECT_TYPES_BY_NAME['Module'] or not obj.get('virtual_bot_ref'):
        return ()
    group = module_groups.get(ref_to_id(obj.get('module_group_ref', '')), {})
    group_name = group.get('name', {}).get('en', '')
    part = next((p for p in _ROBOT_PARTS if group_name.endswith(p)), None)
    if part is None:
        return ()
    side = _SHOULDER_SIDES.get(obj.get('shoulder_side', ''))
    if side:
        return (f'{name} {part} {side}', f'{name} {side} {part}')
    return (f'{name} {part}',)


def _entry_description(snapshot: DataSnapshot, object_type: ObjectType, object_id: str, obj: dict) -> str:
    """The page's English meta description, else the object's own description."""
    text = snapshot.meta_descriptions.get(object_type.name, object_id) or object_description(object_type, obj)
    return _clean_description(text)


def _clean_description(text: str) -> str:
    """Plain description text for an embed, or "" if it can't be shown as-is.

    Descriptions with `{Placeholder}` values are dropped: filling them needs the
    object's scalars, which only the Site resolves (in its meta descriptions).
    """
    if not text or '{' in text:
        return ''
    lines = (' '.join(line.split()) for line in _RICH_TEXT_TAG.sub('', text).splitlines())
    text = '\n'.join(line for line in lines if line)
    if len(text) > MAX_DESCRIPTION_LENGTH:
        text = text[: MAX_DESCRIPTION_LENGTH - 3].rstrip() + '...'
    return text

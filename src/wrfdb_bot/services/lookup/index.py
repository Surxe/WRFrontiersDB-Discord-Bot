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
"""A fuzzy result at or above this score is used as the answer."""
SUGGESTION_MIN_SCORE = 60
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
        for entry in sorted(entries, key=lambda e: (e.priority, e.object_id)):
            for text in (entry.name, *entry.aliases):
                key = to_lookup_key(text)
                if key and entry not in self._entries_by_key[key]:
                    self._entries_by_key[key].append(entry)
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
        matches = self._exact_matches(to_lookup_key(name), object_type)
        if matches:
            return LookupResult(query, matches[0], other_matches=tuple(matches[1:]))

        scored = self._fuzzy(name, object_type, limit=MAX_SUGGESTIONS + 1)
        if scored and scored[0][1] >= FUZZY_MATCH_MIN_SCORE:
            best_matches = self._exact_matches(scored[0][0], object_type)
            return LookupResult(query, best_matches[0], is_fuzzy=True, other_matches=tuple(best_matches[1:]))
        suggestions = [
            self._exact_matches(key, object_type)[0] for key, score in scored if score >= SUGGESTION_MIN_SCORE
        ]
        return LookupResult(query, None, suggestions=tuple(suggestions[:MAX_SUGGESTIONS]))

    def autocomplete(self, text: str, limit: int = 25) -> list[LookupEntry]:
        """Entries for a partly typed query, best first."""
        object_type, name = self._split_known_prefix(text)
        if not to_lookup_key(name):
            return []
        results: list[LookupEntry] = []
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
                    description=_clean_description(object_description(object_type, obj)),
                    aliases=_robot_part_aliases(object_type, obj, name, module_groups),
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


def _clean_description(text: str) -> str:
    """Plain description text for an embed, or "" if it can't be shown as-is.

    Descriptions with `{Placeholder}` values are dropped: filling them needs the
    object's scalars, which the prototype doesn't resolve.
    """
    if not text or '{' in text:
        return ''
    text = ' '.join(_RICH_TEXT_TAG.sub('', text).split())
    if len(text) > MAX_DESCRIPTION_LENGTH:
        text = text[: MAX_DESCRIPTION_LENGTH - 3].rstrip() + '...'
    return text

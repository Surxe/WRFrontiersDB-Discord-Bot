"""Lookup keys: names and queries normalized for matching.

A lookup key is NOT a Site slug, even when the two look the same. Slugs are the
Site's URL path segments, read from the slug map (see wrf_data.site). Lookup keys
exist only inside the lookup index, and are never used to build URLs.
"""

import re

_APOSTROPHES = re.compile(r"['‘’]")
_NON_ALPHANUMERIC = re.compile(r'[^a-z0-9]+')


def to_lookup_key(text: str) -> str:
    """`"Hammer" Petrova` -> `hammer-petrova`; `Kate's Rig` -> `kates-rig`."""
    text = _APOSTROPHES.sub('', text.lower())
    return _NON_ALPHANUMERIC.sub('-', text).strip('-')

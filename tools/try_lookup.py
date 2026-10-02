"""Resolve lookup queries against real data without Discord.

Usage: .venv/bin/python tools/try_lookup.py "Kate Sinclair" "talent:vanguard" ...
Reads DATA_DIR / SITE_URL / SITE_SLUG_MAP_SOURCE from the environment or .env.
"""

import sys

from dotenv import load_dotenv

from wrfdb_bot.options import load_data_options
from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.store import DataStore


def main(queries: list[str]) -> None:
    load_dotenv()
    data_options = load_data_options()
    store = DataStore(DataRepo(data_options.data_dir), data_options.site_url, data_options.site_slug_map_source)
    index = LookupIndex.from_snapshot(store.load())
    for query in queries:
        result = index.resolve(query)
        if result.entry is None:
            suggestions = ', '.join(f'{e.name} ({e.object_type.label})' for e in result.suggestions) or '-'
            print(f'[[{query}]] -> no match; suggestions: {suggestions}')
            continue
        entry = result.entry
        fuzzy = ' (closest match)' if result.is_fuzzy else ''
        print(f'[[{query}]] -> {entry.object_type.label}: {entry.display_name} [{entry.object_id}]{fuzzy}')
        print(f'    url: {entry.url}')
        if entry.description:
            print(f'    {entry.description}')
        for other in result.other_matches:
            print(f'    also: {other.object_type.label}: {other.display_name} -> [[{other.hint}]]')


if __name__ == '__main__':
    main(sys.argv[1:])

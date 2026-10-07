# WRFrontiersDB-Discord-Bot - agent context

A Discord bot answering `[[name]]` / `/wrf` with links to wrf-db.info, from
WRFrontiersDB-Data. See `README.md` for usage, options and layout.

## Terminology - never mix these

- **slug**: ONLY the Site's URL path segment, read from Data's `index/slug_map.json` (`wrf_data/site.py`).
  The bot never generates slugs.
- **lookup key**: a name/query normalized for matching (`services/lookup/lookup_key.py`). It
  can look like a slug but is a different thing; never use it to build URLs.
- **alias**: a full alternative name (`Wyrm Chassis` for a robot part), read from Data's
  `index/aliases.json` (`tools/wrfdb_data/robot_parts.py`). Matches like the name itself (exact,
  fuzzy, hints); the first one is the display name.
- **nickname**: a short name an object answers to (a pilot's first name, `Wyrm Legs`), read from
  Data's `index/nicknames.json` (`tools/wrfdb_data/nicknames.py`); only matches after exact names fail.
- **abbreviation**: a short word for a word of names (`r` -> `relic`, `mk2` -> `mk ii`), read from
  Data's `index/abbreviations.json` (`tools/wrfdb_data/abbreviations.py`). A query's words are
  expanded only when it matches nothing as typed; fuzzy matching then uses the expanded query.
- Aliases, nicknames and abbreviations are `DataSnapshot.names`. The bot never derives any of
  them: Data decides them, so the Site can share them.
- **description**: an object's embed text, `LookupEntry.description` (`index.py`). It is the Site's
  meta description: stats already filled in at max level, markup stripped (else the object's own
  text if it has no `{placeholders}`). To show an object's text anywhere, reuse its entry's
  `description`; never fill placeholders or pick levels in the bot.
- **icon URL**: `LookupEntry.icon_url`, an object's `inventory_icon_path` as a file in the Data
  repo (`wrf_data/textures.py`), pinned to the snapshot's Data commit. The bot never takes icons
  from the Site.
- **id** (Data object id), **type prefix** (`talent:`), **hint** (shortest unique query),
  **service** (a feature/Cog) - as defined in the README.

## Layout rules

- Shared WRF data access goes in `src/wrfdb_bot/wrf_data/`, never inside a service.
- Each feature is a service under `src/wrfdb_bot/services/<name>/` with a `cog.py` `setup()`,
  registered in `SERVICE_EXTENSIONS` (`bot.py`). A scheduled-events service is planned.
- Keep matching logic in `index.py` free of Discord, so it stays testable.

## Working

- Tests: `.venv/bin/python -m pytest`
- Try lookups without Discord:
  `DATA_DIR=/srv/dev/repos/WRFrontiersDB-Data .venv/bin/python tools/try_lookup.py "Kate Sinclair"`
- `personal/` is Ethan's git-excluded notes: `DESIGN.md` (design) and `LONG_TERM.md`
  (deferred ideas; delete an item when it's done).
- Deployment lives in the home-server repo (`hs-wrf-discord-bot.service`,
  `wrf-discord-bot/install.sh`). After a code change, run that installer and check the
  journal for "Logged in as".

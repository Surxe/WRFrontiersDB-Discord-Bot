# WRFrontiersDB-Discord-Bot - agent context

A Discord bot answering `[[name]]` / `/wrf` with links to wrf-db.info, from
WRFrontiersDB-Data. See `README.md` for usage, options and layout.

## Terminology - never mix these

- **slug**: ONLY the Site's URL path segment, read from Data's `index/slug_map.json` (`wrf_data/site.py`).
  The bot never generates slugs.
- **lookup key**: a name/query normalized for matching (`services/lookup/lookup_key.py`). It
  can look like a slug but is a different thing; never use it to build URLs.
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

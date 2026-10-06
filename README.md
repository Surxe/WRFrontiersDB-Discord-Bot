# WRFrontiersDB Discord Bot

A Discord bot for War Robots: Frontiers data from
[WRFrontiersDB-Data](https://github.com/Surxe/WRFrontiersDB-Data). Write `[[Kate Sinclair]]`
in a message and it replies with an embed linking to that object's page on the
[WRFrontiersDB Site](https://wrf-db.info). Inspired by
[dlwikibot](https://github.com/kai8484/dlwikibot).

## Usage

- `[[name]]` anywhere in a message, at most 5 per message. Matching ignores case and
  punctuation (`[[kate sinclair]]`, `[[Hammer Petrova]]`) and corrects small typos (shown
  as "closest match"). Text inside `code` is ignored.
- `[[type:name]]` picks a type when names are shared: `[[Vanguard]]` is the pilot,
  `[[talent:Vanguard]]` is the pilot talent. The bot lists other matches with the exact
  thing to type for each.
- Pilots also answer to their first name: `[[marcus]]` is Marcus Shedd. A first name
  shared by several pilots goes to the premium (hero) one; Marcus Davis needs his full
  name. A real object name always wins over a first name (`[[Fury]]` is the robot), and
  first names are matched exactly, never as typo corrections.
- Robot parts: `[[Alpha]]` is the robot; `[[Alpha Chassis]]`, `[[Alpha Torso]]`,
  `[[Alpha Shoulder Left]]` are its modules.
- `/wrf query:` does the same lookup, with autocomplete.

Indexed types (priority order when names are shared) and their type prefixes:

| Type | Prefixes |
| --- | --- |
| Robot | `robot`, `bot` |
| Pilot | `pilot` |
| Module | `module`, `mod` |
| Pilot Talent | `talent`, `pilot talent` |
| Character Class | `character class`, `robot class` |
| Pilot Class | `pilot class` |
| Faction | `faction` |
| Pilot Personality | `personality`, `pilot personality` |
| Pilot Talent Type | `talent type`, `pilot talent type` |
| Module Group | `module group`, `group` |
| Module Category | `module category`, `category` |
| Currency | `currency` |

## Terminology

These words have exactly one meaning in this repo:

- **id**: an object's id in WRFrontiersDB-Data (`DA_Pilot_Rare_KateSinclair.0`).
- **slug**: only the Site's URL path segment for an object page (`kate-sinclair` in
  `/pilots/kate-sinclair/`), read from Data's slug map (`index/slug_map.json`). The bot
  never generates slugs.
- **lookup key**: a name or query normalized for matching (`kate-sinclair`). It can look
  like a slug but is unrelated, and is never used in URLs.
- **alias**: a full alternative name (`Wyrm Chassis` for a robot part), read from Data's
  `index/aliases.json`. Matches like the name itself; the first is shown in its place.
- **nickname**: a short name an object answers to (a pilot's first name, `Wyrm Legs` for a
  chassis), read from Data's `index/nicknames.json`. Matches only after exact names fail.
- Aliases and nicknames are decided in Data, never by the bot, and never used in URLs.
- **type prefix**: the `type:` part of a query.
- **hint**: the shortest query that reaches one particular object; shown for other matches.
- **service**: one bot feature (a discord.py Cog), switched on with `ENABLED_SERVICES`.

## Setup

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications).
   Under **Bot**, copy the token and turn on **Message Content Intent** (needed for
   `[[...]]`; bots in fewer than 100 servers need no verification for it).
2. Invite it: **OAuth2 -> URL Generator**, scopes `bot` + `applications.commands`,
   permissions Send Messages, Embed Links, Read Message History.
3. Install and configure:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e '.[dev]'
   cp .env.example .env   # fill in DISCORD_BOT_TOKEN, GUILD_IDS, DATA_DIR
   ```
4. Run: `.venv/bin/python -m wrfdb_bot`

`DATA_DIR` is a local clone of WRFrontiersDB-Data. The bot checks it, including its slug
map (`index/slug_map.json`), nicknames (`index/nicknames.json`) and aliases
(`index/aliases.json`), every
`DATA_REFRESH_MINUTES` and reloads whatever changed.
Objects without a slug have no Site page and show up without a link. The pipeline pushes
the slug map before it redeploys the Site, and its run report flags a deploy that fails.

Embed descriptions are the Site's English page meta descriptions, fetched from
`SITE_URL/meta_descriptions.json` at startup and again whenever `SITE_DEPLOY_STATE` (the
pipeline's record of its last Site deploy) names a newer deploy. Objects without one
fall back to their own description.

## Development

- Tests: `.venv/bin/python -m pytest`
- Try lookups without Discord: `DATA_DIR=... .venv/bin/python tools/try_lookup.py "Kate Sinclair" "talent:vanguard"`

```
src/wrfdb_bot/
  __main__.py        entry point (python -m wrfdb_bot)
  options.py         options from env / .env
  bot.py             WrfBot: owns the DataStore, loads enabled services, syncs commands
  wrf_data/          shared WRF data access, used by every service
    data_repo.py     reads a WRFrontiersDB-Data clone
    object_types.py  the indexed types: Site routes, prefixes, names
    site.py          slug map -> page URLs
    meta_descriptions.py  the Site's page meta descriptions (embed text)
    store.py         DataStore / DataSnapshot, refresh on change
  services/
    lookup/          [[name]] + /wrf
      lookup_key.py  name/query normalization
      query_parser.py  [[...]] extraction, type prefixes
      index.py       LookupIndex: exact, priority, aliases, nicknames, fuzzy, hints
      embeds.py      Discord replies
      cog.py         the Cog (Discord glue)
tests/
tools/
```

### Adding a service

Create `src/wrfdb_bot/services/<name>/` with a `cog.py` that defines
`async def setup(bot)`, register it in `SERVICE_EXTENSIONS` in `bot.py`, and enable it
with `ENABLED_SERVICES`. Services read shared data from `bot.data_store.snapshot`. To run
a service as its own process, start a second instance with only that service enabled.

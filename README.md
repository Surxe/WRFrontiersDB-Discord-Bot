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
  thing to type for each, plus a button per other match (or "did you mean" suggestion)
  that posts its answer when clicked.
- Pilots also answer to their first name: `[[marcus]]` is Marcus Shedd. A first name
  shared by several pilots goes to the premium (hero) one; Marcus Davis needs his full
  name. A real object name always wins over a first name (`[[Fury]]` is the robot), and
  first names are matched exactly, never as typo corrections.
- Robot parts: `[[Alpha]]` is the robot; `[[Alpha Chassis]]`, `[[Alpha Torso]]`,
  `[[Alpha Shoulder Left]]` are its modules, and a chassis is also its robot's legs
  (`[[Alpha Legs]]`). A robot's reply also shows its torso ability at max level.
  Variants: `[[Relic Bulgasari Shoulder Mk. II]]`; without the mark it's the highest one.
- Shorthands expand when a query matches nothing as typed: `[[r bulg shoulder mk1]]` is
  Relic Bulgasari Shoulder Mk. I. The list is Data's `index/abbreviations.json`.
- `/wrf query:` does the same lookup, with autocomplete.
- Each embed's footer names the data version it was answered from (`Data 2026-09-29`).
- A Site `/models` link with build codes (`https://wrf-db.info/models?a=<code>&b=<code>`,
  the `builds` service) gets a reply listing each build's parts, linked to their pages. Discord
  already previews the link with the viewer page's title, so the reply carries only the parts.
  At most 5 links per message; links without `a=` are ignored.
- `/wrf-build build:` shows the same for codes typed in directly: one code, two codes to compare
  (`OQ2HQJC75 GYcA04MI0A`, A then B), or a `/models` link. Its reply has no link preview, so it
  links to the model viewer itself. Any site that makes codes with Data's codec can hand out
  that one string for Discord.
- `/about` (the `about` service) shows which data the bot, the Site and the Discount
  Visualizer are on: each frontend's Data commit from its `/deploy.json`, and whether it is
  the same as, behind or ahead of the bot's `DATA_DIR`.

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
- **abbreviation**: a short word for a word of names (`r` -> `relic`, `bulg` -> `bulgasari`),
  read from Data's `index/abbreviations.json`. Expands a query that matched nothing as typed.
- **nickname**: a short name an object answers to (a pilot's first name, `Wyrm Legs` for a
  chassis), read from Data's `index/nicknames.json`. Matches only after exact names fail.
- Aliases, nicknames and abbreviations are decided in Data, never by the bot, and never used
  in URLs.
- **icon URL**: an object's icon (`inventory_icon_path`) as a file in the Data repo,
  `DATA_RAW_URL/<commit>/textures<path>.png`, pinned to the commit of `DATA_DIR`. Shown as
  the embed thumbnail; built only when that file exists in the clone.
- **type prefix**: the `type:` part of a query.
- **hint**: the shortest query that reaches one particular object; shown for other matches.
- **build code**: the short string for one robot build in the Site's `/models?a=<code>` links.
  The format and the codec belong to Data (`index/build_codes.json`,
  `tools/wrfdb_data/build_code.py`); the bot loads both from `DATA_DIR` and never encodes or
  decodes on its own.
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
map (`index/slug_map.json`), nicknames, aliases and abbreviations (`index/nicknames.json`,
`aliases.json`, `abbreviations.json`) and build-code registry (`index/build_codes.json`, decoded
with the clone's `tools/wrfdb_data/build_code.py`), every `DATA_REFRESH_MINUTES` and reloads
whatever changed.
Objects without a slug have no Site page and show up without a link. The pipeline pushes
the slug map before it redeploys the Site, and its run report flags a deploy that fails.

Embed descriptions are the Site's English page meta descriptions, fetched from
`SITE_URL/meta_descriptions.json` at startup and again whenever `SITE_DEPLOY_STATE` (the
pipeline's record of its last Site deploy) names a newer deploy (`run_id`). Objects without
one fall back to their own description. Armor modules (chassis, torsos, shoulders) show
their stats as inline embed fields instead of description lines, from the same JSON's
`stat_summaries`. That record also says which Data commit the Site
was built from; the bot logs it and warns while the Site's data version differs from
`DATA_DIR`'s.

Embed thumbnails are object icons, linked straight from the Data repo at the commit
`DATA_DIR` is on (`DATA_RAW_URL`), so they always match the data and need no Site deploy.

Build codes and `/models` links rely on the Site being deployed with the bot's Data version or
newer. A code made from parts the bot's `DATA_DIR` doesn't have yet gets a "newer than the
bot's data" reply instead of a build. The Site reads codes the same way, so a Site deployed
from older data than the code shows its default robot.

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
    textures.py      texture paths -> icon URLs in the Data repo
    meta_descriptions.py  the Site's page meta descriptions (embed text)
    deploys.py       the frontends' deploy records: which Data commit they serve
    build_codes.py   Data's build-code codec + registry, loaded from DATA_DIR
    store.py         DataStore / DataSnapshot, refresh on change
  services/
    lookup/          [[name]] + /wrf
      lookup_key.py  name/query normalization
      query_parser.py  [[...]] extraction, type prefixes
      index.py       LookupIndex: exact, priority, aliases, nicknames, fuzzy, hints
      embeds.py      Discord replies
      views.py       Buttons for other matches / suggestions (clicked = looked up)
      cog.py         the Cog (Discord glue)
    builds/          /models build-code links + /wrf-build
      links.py       link + /wrf-build input parsing, decoding, part names (Discord-free)
      embeds.py      Discord replies
      cog.py         the Cog
    about/           /about
      status.py      the bot's and the frontends' Data commits (Discord-free)
      cog.py         the Cog
tests/
tools/
```

### Adding a service

Create `src/wrfdb_bot/services/<name>/` with a `cog.py` that defines
`async def setup(bot)`, register it in `SERVICE_EXTENSIONS` in `bot.py`, and enable it
with `ENABLED_SERVICES`. Services read shared data from `bot.data_store.snapshot`. To run
a service as its own process, start a second instance with only that service enabled.

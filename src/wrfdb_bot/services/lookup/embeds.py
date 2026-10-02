"""Discord replies for lookup results."""

import discord

from .index import LookupResult

EMBED_COLOUR = discord.Colour(0x3B82F6)
MAX_OTHER_MATCHES_SHOWN = 5


def reply_kwargs(results: list[LookupResult]) -> dict:
    """Arguments for send/reply: one embed per answered query, a text line per miss."""
    embeds = [result_embed(r) for r in results if r.entry is not None]
    misses = [no_match_line(r) for r in results if r.entry is None]
    return {
        'content': '\n'.join(misses) or None,
        'embeds': embeds,
        # Queries are echoed back; never let them ping anyone.
        'allowed_mentions': discord.AllowedMentions.none(),
    }


def result_embed(result: LookupResult) -> discord.Embed:
    entry = result.entry
    assert entry is not None
    embed = discord.Embed(
        title=entry.display_name,
        url=entry.url,
        description=entry.description or None,
        colour=EMBED_COLOUR,
    )
    if result.other_matches:
        lines = [f'{o.object_type.label}: `[[{o.hint}]]`' for o in result.other_matches[:MAX_OTHER_MATCHES_SHOWN]]
        hidden = len(result.other_matches) - MAX_OTHER_MATCHES_SHOWN
        if hidden > 0:
            lines.append(f'...and {hidden} more')
        embed.add_field(name='Also matches', value='\n'.join(lines), inline=False)

    footer = entry.object_type.label
    if result.is_fuzzy:
        footer += f' - closest match for "{result.query}"'
    if entry.url is None:
        footer += ' - no page on the site yet'
    embed.set_footer(text=footer)
    return embed


def no_match_line(result: LookupResult) -> str:
    query = discord.utils.escape_markdown(result.query)
    line = f'No match for **{query}**.'
    if result.suggestions:
        line += ' Did you mean: ' + ', '.join(f'`[[{s.hint}]]`' for s in result.suggestions) + '?'
    return line

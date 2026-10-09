"""Discord replies for `/models` build links.

Discord already previews a pasted link itself with the page's (fixed) title and
description, so a reply to one adds only what the preview lacks: the parts. A
`/wrf-build` reply has no preview, so its embed links to the model viewer.
"""

import discord

from .links import BuildLink, Part

EMBED_COLOUR = discord.Colour(0x3B82F6)


VIEWER_TITLE = 'Open in the model viewer'


def reply_kwargs(links: list[BuildLink], data_version: str = '', viewer_url: str | None = None) -> dict:
    """Arguments for send/reply: one embed per readable link, a text line per unreadable one.
    `viewer_url` titles the (single) embed with a link to the model viewer."""
    embeds = [build_embed(link, data_version, viewer_url) for link in links if link.builds]
    problems = [problem_line(link, data_version) for link in links if not link.builds]
    return {
        'content': '\n'.join(problems) or None,
        'embeds': embeds,
        'allowed_mentions': discord.AllowedMentions.none(),
    }


def build_embed(link: BuildLink, data_version: str = '', viewer_url: str | None = None) -> discord.Embed:
    titles = ('Build A', 'Build B') if len(link.builds) > 1 else ('Build',)
    sections = [f'**{title}**\n' + '\n'.join(map(part_line, build)) for title, build in zip(titles, link.builds)]
    embed = discord.Embed(description='\n\n'.join(sections), colour=EMBED_COLOUR)
    if viewer_url:
        embed.title = VIEWER_TITLE
        embed.url = viewer_url
    if data_version:
        embed.set_footer(text=f'Data {data_version}')
    return embed


def part_line(part: Part) -> str:
    name = discord.utils.escape_markdown(part.name)
    return f'{part.slot}: [{name}]({part.url})' if part.url else f'{part.slot}: {name}'


def problem_line(link: BuildLink, data_version: str = '') -> str:
    # Shown in inline code, where markdown escapes would show literally; only a backtick can break out.
    code = ' / '.join(link.codes).replace('`', "'")
    if link.too_new:
        data = f' (Data {data_version})' if data_version else ''
        return f'Build `{code}` uses parts newer than the bot\'s data{data}; try again after the next update.'
    return f'`{code}` isn\'t a build code.'

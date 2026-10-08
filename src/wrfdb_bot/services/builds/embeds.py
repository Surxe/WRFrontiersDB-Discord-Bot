"""Discord replies for `/models` build links.

Discord already previews the link itself with the page's (fixed) title and
description, so a reply adds only what the preview lacks: the parts.
"""

import discord

from .links import BuildLink, Part

EMBED_COLOUR = discord.Colour(0x3B82F6)


def reply_kwargs(links: list[BuildLink], data_version: str = '') -> dict:
    """Arguments for send/reply: one embed per readable link, a text line per unreadable one."""
    embeds = [build_embed(link, data_version) for link in links if link.builds]
    problems = [problem_line(link, data_version) for link in links if not link.builds]
    return {
        'content': '\n'.join(problems) or None,
        'embeds': embeds,
        'allowed_mentions': discord.AllowedMentions.none(),
    }


def build_embed(link: BuildLink, data_version: str = '') -> discord.Embed:
    titles = ('Build A', 'Build B') if len(link.builds) > 1 else ('Build',)
    sections = [f'**{title}**\n' + '\n'.join(map(part_line, build)) for title, build in zip(titles, link.builds)]
    embed = discord.Embed(description='\n\n'.join(sections), colour=EMBED_COLOUR)
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

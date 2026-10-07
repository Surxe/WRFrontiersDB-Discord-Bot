"""Buttons under a lookup reply: one per other match or suggestion, answering it when clicked.

A button carries its object in its custom id (`wrf:lookup:<type>:<id>`) and is a
`DynamicItem`, so it keeps working after the bot restarts; nothing is held in memory.
"""

import re
from typing import TYPE_CHECKING

import discord

from .index import LookupEntry, LookupResult

if TYPE_CHECKING:
    from .cog import LookupCog

MAX_BUTTONS = 25
"""Discord's limit: 5 rows of 5."""
MAX_LABEL_LENGTH = 80


class LookupButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r'wrf:lookup:(?P<type_name>[A-Za-z]+):(?P<object_id>.+)',
):
    def __init__(self, type_name: str, object_id: str, label: str = '?'):
        super().__init__(
            discord.ui.Button(
                label=label[:MAX_LABEL_LENGTH],
                style=discord.ButtonStyle.secondary,
                custom_id=f'wrf:lookup:{type_name}:{object_id}',
            )
        )
        self.type_name = type_name
        self.object_id = object_id

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]
    ) -> 'LookupButton':
        return cls(match['type_name'], match['object_id'], item.label or '?')

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: 'LookupCog | None' = interaction.client.get_cog('LookupCog')  # type: ignore[attr-defined]
        if cog is None:
            await interaction.response.send_message('Lookups are disabled.', ephemeral=True)
            return
        await cog.answer_click(interaction, self.type_name, self.object_id)


def lookup_view(results: list[LookupResult]) -> discord.ui.View | None:
    """Buttons for the results' other matches and suggestions, or None if there are none."""
    answered = [r.entry for r in results if r.entry is not None]
    entries: list[LookupEntry] = []
    for result in results:
        for entry in (*result.other_matches, *result.suggestions):
            if entry not in answered and entry not in entries:
                entries.append(entry)
    if not entries:
        return None
    entries = entries[:MAX_BUTTONS]
    names = [e.display_name for e in entries]
    view = discord.ui.View(timeout=None)
    for entry in entries:
        label = entry.display_name
        if names.count(label) > 1:
            label += f' ({entry.object_type.label})'
        view.add_item(LookupButton(entry.object_type.name, entry.object_id, label))
    return view

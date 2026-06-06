"""Discord adapters for the dibs feature."""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


async def _call(command, *args, **kwargs):
    callback = getattr(command, "callback", command)
    return await callback(*args, **kwargs)


class DibsCog(commands.Cog, name="Dibs"):
    """Dibs prefix and slash commands.

    Command behavior currently delegates to compatibility callbacks while the
    persistence-heavy implementation is moved behind the feature service.
    """

    def __init__(self, runtime):
        self.runtime = runtime

    @commands.command(name="dibs_data")
    async def dibs_data(self, ctx):
        await _call(self.runtime.dibs_data_command, ctx)

    @app_commands.command(
        name="dibs", description="Claim dibs on an item from the distribution list"
    )
    @app_commands.describe(item="The item you want to claim", quantity="Optional number of items")
    async def dibs(
        self, interaction: discord.Interaction, item: str, quantity: Optional[int] = None
    ):
        await _call(self.runtime.dibs, interaction, item, quantity)

    @dibs.autocomplete("item")
    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.runtime.item_autocomplete(interaction, current)

    @app_commands.command(
        name="custom_dibs", description="Claim a custom dibs entry using free-form text"
    )
    @app_commands.describe(text="The custom dibs text", quantity="Optional number of items")
    async def custom_dibs(
        self, interaction: discord.Interaction, text: str, quantity: Optional[int] = None
    ):
        await _call(self.runtime.custom_dibs, interaction, text, quantity)

    @app_commands.command(name="undibs", description="Remove one or all of your dibs")
    @app_commands.describe(item="The item to remove, or 'all' to clear all")
    async def undibs(self, interaction: discord.Interaction, item: str):
        await _call(self.runtime.undibs, interaction, item)

    @undibs.autocomplete("item")
    async def undibs_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.runtime.undibs_autocomplete(interaction, current)

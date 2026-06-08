"""Discord adapters for the event tracking feature."""

from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands


async def _call(command, *args, **kwargs):
    callback = getattr(command, "callback", command)
    return await callback(*args, **kwargs)


class _InteractionEventContext:
    """Expose the context surface used by the existing event creation callbacks."""

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.author = interaction.user
        self.channel = interaction.channel or SimpleNamespace(id=interaction.channel_id)
        self.message = SimpleNamespace(id=interaction.id, created_at=interaction.created_at)

    async def send(self, content=None, *, embed=None):
        await self.interaction.response.send_message(content, embed=embed)
        return await self.interaction.original_response()


class EventCog(commands.Cog, name="Events"):
    """Prefix commands and listeners owned by event tracking."""

    def __init__(
        self,
        runtime,
        event_command_name: str = "event",
        event_channel_id: str | None = None,
    ):
        self.runtime = runtime
        self.event_command_name = event_command_name
        self.event_channel_id = event_channel_id
        self.event.name = event_command_name

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        await _call(self.runtime.on_reaction_add, reaction, user)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        await _call(self.runtime.on_reaction_remove, reaction, user)

    @commands.command(name="dungeon")
    async def dungeon(self, ctx, *, dungeon_name: str):
        await _call(self.runtime.dungeon, ctx, dungeon_name=dungeon_name)

    @commands.command(name="miniboss", aliases=["mini"])
    async def miniboss(self, ctx, *, miniboss_name: str):
        await _call(self.runtime.miniboss, ctx, miniboss_name=miniboss_name)

    @commands.command(name="boss", aliases=["main", "mainboss"])
    async def boss(self, ctx, *, boss_name: str):
        await _call(self.runtime.boss, ctx, boss_name=boss_name)

    @commands.command(name="t8")
    async def t8(self, ctx, *, t8_name: str):
        await _call(self.runtime.t8, ctx, t8_name=t8_name)

    @commands.command(name="omniboss", aliases=["omni"])
    async def omniboss(self, ctx, *, omniboss_name: str):
        await _call(self.runtime.omniboss, ctx, omniboss_name=omniboss_name)

    @app_commands.command(name="event", description="Create a new tracked event")
    @app_commands.describe(type="The kind of event to create", name="The event name")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Dungeon", value="dungeon"),
            app_commands.Choice(name="Miniboss", value="miniboss"),
            app_commands.Choice(name="Boss", value="boss"),
            app_commands.Choice(name="T8", value="t8"),
            app_commands.Choice(name="Omniboss", value="omniboss"),
        ]
    )
    async def event(
        self,
        interaction: discord.Interaction,
        type: str,
        name: app_commands.Range[str, 1, 200],
    ):
        if self.event_channel_id and str(interaction.channel_id) != self.event_channel_id:
            await interaction.response.send_message(
                f"`/{self.event_command_name}` can only be used in the designated event channel.",
                ephemeral=True,
            )
            return

        event_name = name.strip() if name else ""
        event_commands = {
            "dungeon": (self.runtime.dungeon, "dungeon_name"),
            "miniboss": (self.runtime.miniboss, "miniboss_name"),
            "boss": (self.runtime.boss, "boss_name"),
            "t8": (self.runtime.t8, "t8_name"),
            "omniboss": (self.runtime.omniboss, "omniboss_name"),
        }

        if type not in event_commands or not event_name or len(event_name) > 200:
            await interaction.response.send_message(
                "Please provide both a valid event type and an event name between 1 and 200 "
                "characters.",
                ephemeral=True,
            )
            return

        command, name_parameter = event_commands[type]
        await _call(
            command,
            _InteractionEventContext(interaction),
            **{name_parameter: event_name},
        )

    @commands.command(name="add_users")
    async def add_users(self, ctx, event_id: str, multiplier: float, *members: discord.Member):
        await _call(self.runtime.add_users, ctx, event_id, multiplier, *members)

    @add_users.error
    async def add_users_error(self, ctx, error):
        await _call(self.runtime.add_users_error, ctx, error)

    @commands.command(name="summary")
    async def summary(self, ctx, *, args: str = ""):
        await _call(self.runtime.summary, ctx, args=args)

    @commands.command(name="data")
    async def data(self, ctx, *, args: str = ""):
        await _call(self.runtime.data_command, ctx, args=args)

    @commands.command(name="delete_event")
    async def delete_event(self, ctx, event_id: str):
        await _call(self.runtime.delete_event, ctx, event_id)

    @delete_event.error
    async def delete_event_error(self, ctx, error):
        await _call(self.runtime.delete_event_error, ctx, error)

    @commands.command(name="missing", aliases=["whoismissing"])
    async def missing(self, ctx, event_id1: str = None, event_id2: str = None):
        await _call(self.runtime.missing, ctx, event_id1, event_id2)

    @missing.error
    async def missing_error(self, ctx, error):
        await _call(self.runtime.missing_error, ctx, error)

    @commands.command(name="backfill")
    async def backfill(self, ctx, event_type: str, message_id: int):
        await _call(self.runtime.backfill, ctx, event_type, message_id)

    @commands.command(name="rename", aliases=["rename_event"])
    async def rename(self, ctx, event_id: str, *, new_name: str):
        await _call(self.runtime.rename_event, ctx, event_id, new_name=new_name)

    @rename.error
    async def rename_error(self, ctx, error):
        await _call(self.runtime.rename_event_error, ctx, error)

    @commands.command(name="reminders")
    async def reminders(self, ctx, action: str = None):
        await _call(self.runtime.reminders, ctx, action)

    @commands.command(name="help_events")
    async def help_events(self, ctx):
        await _call(self.runtime.help_events, ctx)

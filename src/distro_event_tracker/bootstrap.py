"""Runtime composition helpers."""

from types import ModuleType

from discord.ext import commands


async def install_cogs(
    target_bot: commands.Bot,
    runtime: ModuleType,
    dibs_channel_id: str | None,
    event_command_name: str = "event",
    event_channel_id: str | None = None,
) -> None:
    """Replace compatibility registrations with feature-owned Cogs."""
    from .dibs.cog import DibsCog
    from .events.cog import EventCog

    for command in list(target_bot.commands):
        if command.name != "help":
            target_bot.remove_command(command.name)

    target_bot.tree.clear_commands(guild=None)

    # Compatibility decorators register instance event handlers. Remove the
    # reaction handlers so only the EventCog listeners receive these events.
    target_bot.__dict__.pop("on_reaction_add", None)
    target_bot.__dict__.pop("on_reaction_remove", None)

    await target_bot.add_cog(EventCog(runtime, event_command_name, event_channel_id))
    await target_bot.add_cog(DibsCog(runtime))

    if not dibs_channel_id:
        for command_name in ("dibs", "custom_dibs", "undibs"):
            target_bot.tree.remove_command(command_name)


def create_bot() -> commands.Bot:
    """Return the configured bot.

    Feature Cogs are installed by the bot's setup hook immediately before the
    application-command tree is synchronized.
    """
    from .bot import bot

    return bot

"""Discord adapter for reaction-based event planning."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .planning import (
    NUMBER_EMOJIS,
    EventPlan,
    block_counts,
    build_blocks,
    overlapping_users,
    parse_local_datetime,
    schedule_indices,
    whole_event_users,
)
from .planning_display import (
    LOCAL_TIME_NOTE,
    field_pages,
    local_availability,
    time_range,
    timestamp,
)
from .planning_draft import PlanningDraft
from .planning_persistence import format_planning_footer, parse_planning_footer
from .planning_service import PlanningService
from .planning_wizard import PlanningWizard

logger = logging.getLogger(__name__)


class PlanningCog(commands.Cog, name="Planning"):
    """Own planning commands and their availability reactions."""

    plan = app_commands.Group(name="plan", description="Create and schedule event-planning polls")

    def __init__(
        self,
        bot: commands.Bot,
        planning_channel_id: str,
        service: PlanningService | None = None,
    ) -> None:
        self.bot = bot
        self.planning_channel_id = planning_channel_id
        self.service = service or PlanningService()
        self._locks: dict[int, asyncio.Lock] = {}

    async def _require_planning_channel(self, interaction: discord.Interaction) -> bool:
        if str(interaction.channel_id) == self.planning_channel_id:
            return True
        await interaction.response.send_message(
            "`/plan` can only be used in the designated planning channel.", ephemeral=True
        )
        return False

    @staticmethod
    def _blocks(plan: EventPlan):
        return build_blocks(plan.starts_at, plan.ends_at)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return timestamp(value)

    def _embed(self, plan: EventPlan) -> discord.Embed:
        blocks = self._blocks(plan)
        title_state = (
            "CANCELLED" if plan.cancelled else "SCHEDULED" if not plan.is_open else "PLANNING"
        )
        embed = discord.Embed(title=f"{title_state} · {plan.name}", color=discord.Color.blurple())
        embed.add_field(name="Leader", value=f"<@{plan.leader_id}>", inline=True)
        if plan.event_type:
            embed.add_field(name="Type", value=plan.event_type, inline=True)
        if plan.minimum_people is not None and plan.maximum_people is not None:
            party_size = f"Target: {plan.minimum_people}–{plan.maximum_people} people"
        elif plan.minimum_people is not None:
            party_size = f"Minimum: {plan.minimum_people} people"
        elif plan.maximum_people is not None:
            party_size = f"Preferred maximum: {plan.maximum_people} people"
        else:
            party_size = None
        if party_size:
            embed.add_field(name="Party size", value=party_size, inline=False)
        if plan.scheduled_start is not None and plan.scheduled_end is not None:
            embed.add_field(
                name="Scheduled time",
                value=f"{self._timestamp(plan.scheduled_start)} – {self._timestamp(plan.scheduled_end)}",
                inline=False,
            )
        else:
            embed.add_field(
                name="Availability window",
                value=f"{self._timestamp(plan.starts_at)} – {self._timestamp(plan.ends_at)}",
                inline=False,
            )
        counts = block_counts(plan, len(blocks))
        rows = []
        for index, (block, count) in enumerate(zip(blocks, counts)):
            status = ""
            if plan.minimum_people is not None:
                status = (
                    " · minimum met"
                    if count >= plan.minimum_people
                    else f" · needs {plan.minimum_people - count} more"
                )
            if plan.maximum_people is not None and count > plan.maximum_people:
                status += f" · {count - plan.maximum_people} above preferred maximum"
            rows.append(
                f"{NUMBER_EMOJIS[index]} {time_range(block.start, block.end)} — **{count} available**{status}"
            )
        for page, value in enumerate(field_pages(rows)):
            embed.add_field(
                name=(
                    f"Availability · {len(plan.availability)} people responded"
                    if page == 0
                    else "Availability (continued)"
                ),
                value=value,
                inline=False,
            )
        if plan.details:
            embed.add_field(name="Details", value=plan.details, inline=False)
        if plan.is_open:
            embed.description = (
                "React to every 30-minute block you can attend in full. Remove a reaction if "
                "your availability changes. The leader schedules with `/plan schedule`."
            )
        elif plan.cancelled:
            embed.description = "Planning is closed."
        else:
            start_index, end_index = schedule_indices(
                plan, plan.scheduled_start, plan.scheduled_end
            )
            whole = len(whole_event_users(plan, start_index, end_index))
            overlap = len(overlapping_users(plan, start_index, end_index))
            embed.description = f"Planning is closed. **{whole} available throughout · {overlap} available for some portion.**"
        embed.description = f"{LOCAL_TIME_NOTE}\n\n{embed.description}"
        embed.set_footer(text=format_planning_footer(plan))
        return embed

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Restore planning cards from Discord history and their current reactions."""
        channel = self.bot.get_channel(int(self.planning_channel_id))
        if channel is None:
            return
        try:
            async for message in channel.history(limit=200):
                if message.author != self.bot.user or not message.embeds:
                    continue
                plan = parse_planning_footer(
                    message.embeds[0].footer.text,
                    message_id=message.id,
                    channel_id=channel.id,
                )
                if plan is None:
                    continue
                self.service.add(plan)
                if plan.is_open:
                    for index, emoji in enumerate(NUMBER_EMOJIS[: len(self._blocks(plan))]):
                        reaction = discord.utils.get(message.reactions, emoji=emoji)
                        if reaction is None:
                            continue
                        async for user in reaction.users():
                            if not user.bot:
                                self.service.update_reaction(message.id, user.id, index, True)
        except (discord.Forbidden, discord.HTTPException):
            return

    @plan.command(name="create", description="Post a reaction-based availability poll")
    @app_commands.describe(
        name="Event name",
        event_type="Optional event category",
        minimum_people="Optional minimum viable group size",
        maximum_people="Optional preferred group size",
        details="Optional meeting details",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        event_type: str | None = None,
        minimum_people: int | None = None,
        maximum_people: int | None = None,
        details: str | None = None,
    ) -> None:
        if not await self._require_planning_channel(interaction):
            return
        try:
            draft = PlanningDraft(
                leader_id=interaction.user.id,
                channel_id=interaction.channel_id,
                name=name.strip(),
                event_type=event_type.strip() if event_type else None,
                minimum_people=minimum_people,
                maximum_people=maximum_people,
                details=details.strip() if details else None,
            )
            draft.validate_details()
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        wizard = PlanningWizard(self, draft)
        await interaction.response.send_message(
            embed=discord.Embed(description=wizard.content), view=wizard, ephemeral=True
        )
        wizard.message = await interaction.original_response()

    async def post_draft(self, interaction: discord.Interaction, draft: PlanningDraft) -> None:
        """Publish once after validation; report partial or uncertain writes explicitly."""
        message = None
        try:
            draft.validate_details()
            draft.validate_times(datetime.now(timezone.utc))
            if (
                str(interaction.channel_id) != self.planning_channel_id
                or interaction.channel_id != draft.channel_id
            ):
                raise ValueError("Please start a new draft in the designated planning channel.")
            channel = interaction.channel
            if interaction.guild is None or channel is None:
                raise ValueError("Please use a server planning channel.")
            member = interaction.guild.get_member(draft.leader_id)
            permissions = channel.permissions_for(member) if member else None
            bot_member = interaction.guild.me or interaction.guild.get_member(self.bot.user.id)
            if bot_member is None:
                raise ValueError(
                    "The bot is not available in this server. Please try again shortly."
                )
            bot_permissions = channel.permissions_for(bot_member)
            if (
                not permissions
                or not permissions.view_channel
                or not permissions.use_application_commands
            ):
                raise ValueError("You no longer have access to use planning in this channel.")
            if not all(
                getattr(bot_permissions, name)
                for name in (
                    "view_channel",
                    "send_messages",
                    "embed_links",
                    "add_reactions",
                    "read_message_history",
                )
            ):
                raise ValueError(
                    "The bot needs View Channel, Send Messages, Embed Links, Add Reactions, and Read Message History here."
                )
            plan = draft.to_plan(uuid.uuid4().hex[:12])
            # Reserve space for scheduled timestamps before publishing a durable card.
            future = replace(plan, scheduled_start=plan.starts_at, scheduled_end=plan.ends_at)
            if len(format_planning_footer(future)) > 2048 or len(self._embed(future)) > 6000:
                raise ValueError(
                    "This poll is too large for Discord. Please shorten its name or details and start again."
                )
            message = await channel.send(
                embed=self._embed(plan), allowed_mentions=discord.AllowedMentions.none()
            )
            plan.message_id = message.id
            self.service.add(plan)
            for emoji in NUMBER_EMOJIS[: len(self._blocks(plan))]:
                await message.add_reaction(emoji)
        except ValueError as exc:
            await interaction.edit_original_response(content=str(exc), embed=None, view=None)
            return
        except discord.HTTPException:
            logger.exception("Planning poll publication failed channel=%s", draft.channel_id)
            if message is not None:
                result = f"The poll was posted, but some reaction buttons could not be added. Check [the poll]({message.jump_url}); do not post it again."
            else:
                result = "Discord did not confirm publication. Check the planning channel before starting a new draft to avoid duplicates."
            await interaction.edit_original_response(content=result, embed=None, view=None)
            return
        await interaction.edit_original_response(
            content=f"Poll posted: {message.jump_url}", embed=None, view=None
        )

    @plan.command(name="schedule", description="Choose the final time and notify available members")
    @app_commands.describe(
        message_id="Planning message ID",
        starts="YYYY-MM-DD HH:MM in the timezone chosen for this plan (older plans: Pacific)",
        ends="YYYY-MM-DD HH:MM in the timezone chosen for this plan (older plans: Pacific)",
    )
    async def schedule(
        self, interaction: discord.Interaction, message_id: str, starts: str, ends: str
    ) -> None:
        if not await self._require_planning_channel(interaction):
            return
        try:
            plan = self.service.plans[int(message_id)]
        except (KeyError, ValueError):
            await interaction.response.send_message(
                "I could not find an open planning poll with that message ID.", ephemeral=True
            )
            return
        if (
            interaction.user.id != plan.leader_id
            and not interaction.user.guild_permissions.manage_messages
        ):
            await interaction.response.send_message(
                "Only the planning leader or a moderator can schedule this event.", ephemeral=True
            )
            return
        try:
            scheduled_start = parse_local_datetime(starts, plan.input_timezone)
            scheduled_end = parse_local_datetime(ends, plan.input_timezone)
            blocks = self._blocks(plan)
            start_index, end_index = schedule_indices(plan, scheduled_start, scheduled_end)
        except ValueError as exc:
            await interaction.response.send_message(
                f"{exc} Enter times in {plan.input_timezone}, on a 30-minute boundary.",
                ephemeral=True,
            )
            return
        lock = self._locks.setdefault(plan.message_id, asyncio.Lock())
        async with lock:
            if not plan.is_open:
                await interaction.response.send_message(
                    "This planning poll is already closed.", ephemeral=True
                )
                return
            plan.scheduled_start, plan.scheduled_end = scheduled_start, scheduled_end
            recipients = overlapping_users(plan, start_index, end_index)
            channel = self.bot.get_channel(plan.channel_id)
            message = await channel.fetch_message(plan.message_id) if channel else None
            if message:
                await message.edit(embed=self._embed(plan))
            await interaction.response.send_message(
                f"Scheduled and notifying {len(recipients)} available member(s).", ephemeral=True
            )
            for user_id, selected in recipients.items():
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    await user.send(
                        f"**{plan.name}** is scheduled for {self._timestamp(scheduled_start)}–{self._timestamp(scheduled_end)}. "
                        f"{LOCAL_TIME_NOTE}\nYour indicated availability: {local_availability(selected, blocks)}. "
                        f"[Open event]({message.jump_url if message else ''})"
                    )
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    continue

    @plan.command(name="cancel", description="Close a planning poll without scheduling it")
    async def cancel(self, interaction: discord.Interaction, message_id: str) -> None:
        if not await self._require_planning_channel(interaction):
            return
        plan = self.service.plans.get(int(message_id)) if message_id.isdigit() else None
        if plan is None:
            await interaction.response.send_message(
                "I could not find that planning poll.", ephemeral=True
            )
            return
        if (
            interaction.user.id != plan.leader_id
            and not interaction.user.guild_permissions.manage_messages
        ):
            await interaction.response.send_message(
                "Only the planning leader or a moderator can cancel this poll.", ephemeral=True
            )
            return
        if not plan.is_open:
            await interaction.response.send_message(
                "This planning poll is already closed.", ephemeral=True
            )
            return
        plan.cancelled = True
        channel = self.bot.get_channel(plan.channel_id)
        if channel:
            message = await channel.fetch_message(plan.message_id)
            await message.edit(embed=self._embed(plan))
        await interaction.response.send_message("Planning poll cancelled.", ephemeral=True)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user) -> None:
        await self._record_reaction(reaction, user, added=True)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user) -> None:
        await self._record_reaction(reaction, user, added=False)

    async def _record_reaction(self, reaction, user, *, added: bool) -> None:
        if user.bot:
            return
        try:
            index = NUMBER_EMOJIS.index(str(reaction.emoji))
        except ValueError:
            return
        if not self.service.update_reaction(reaction.message.id, user.id, index, added):
            return
        plan = self.service.plans[reaction.message.id]
        await reaction.message.edit(embed=self._embed(plan))

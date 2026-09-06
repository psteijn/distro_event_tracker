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
    MAX_PLAN_BLOCKS,
    NUMBER_EMOJIS,
    EventPlan,
    block_counts,
    build_blocks,
    overlapping_users,
    schedule_indices,
    schedule_slot_indices,
    whole_event_users,
)
from .planning_display import (
    LOCAL_TIME_NOTE,
    field_pages,
    scheduled_availability_message,
    time_range,
    timestamp,
)
from .planning_draft import PlanningDraft
from .planning_persistence import parse_planning_card, parse_planning_footer
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
        embed.add_field(name="Plan ID", value=plan.id, inline=True)
        embed.add_field(name="Leader", value=f"<@{plan.leader_id}>", inline=True)
        embed.add_field(name="Input timezone", value=plan.input_timezone, inline=True)
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
        embed.add_field(
            name="Availability window",
            value=f"{self._timestamp(plan.starts_at)} – {self._timestamp(plan.ends_at)}",
            inline=False,
        )
        if plan.scheduled_start is not None and plan.scheduled_end is not None:
            embed.add_field(
                name="Scheduled time",
                value=f"{self._timestamp(plan.scheduled_start)} – {self._timestamp(plan.scheduled_end)}",
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
                f":{index + 1}: **{index + 1}** · {time_range(block.start, block.end)} — **{count} available**{status}"
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
                "your availability changes. Schedule slots with `/plan schedule start:3 end:5` (both inclusive)."
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
        return embed

    def _scheduled_notification_embed(
        self,
        plan: EventPlan,
        *,
        selected: set[int],
        blocks,
        start_index: int,
        end_index: int,
        guild_name: str,
        jump_url: str,
    ) -> discord.Embed:
        """Build a recipient-specific DM for a newly scheduled event."""
        embed = discord.Embed(
            title=f"{plan.name} is happening!",
            description=f"{guild_name} · Led by <@{plan.leader_id}>",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="When",
            value=time_range(plan.scheduled_start, plan.scheduled_end),
            inline=False,
        )
        embed.add_field(
            name="Your availability",
            value=scheduled_availability_message(selected, blocks, start_index, end_index),
            inline=False,
        )
        if plan.details:
            embed.add_field(name="Details", value=plan.details, inline=False)
        embed.add_field(name="Event plan", value=f"[View event plan]({jump_url})", inline=False)
        embed.set_footer(text=LOCAL_TIME_NOTE)
        return embed

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Restore planning cards from Discord history and their current reactions."""
        channel = self.bot.get_channel(int(self.planning_channel_id))
        if channel is None:
            return
        try:
            async for message in channel.history(limit=None):
                if message.author != self.bot.user or not message.embeds:
                    continue
                plan = parse_planning_footer(
                    message.embeds[0].footer.text,
                    message_id=message.id,
                    channel_id=channel.id,
                )
                if plan is None:
                    plan = parse_planning_card(
                        message.embeds[0], message_id=message.id, channel_id=channel.id
                    )
                if plan is None:
                    continue
                self.service.add(plan)
                if plan.is_open:
                    for index in range(len(self._blocks(plan))):
                        reaction = next(
                            (
                                reaction
                                for reaction in message.reactions
                                if self._reaction_index(reaction.emoji) == index
                            ),
                            None,
                        )
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
            if len(self._blocks(plan)) > MAX_PLAN_BLOCKS or len(self._embed(plan)) > 6000:
                raise ValueError(
                    "This poll is too large for Discord. Please shorten its name or details and start again."
                )
            message = await channel.send(
                embed=self._embed(plan), allowed_mentions=discord.AllowedMentions.none()
            )
            plan.message_id = message.id
            self.service.add(plan)
            for emoji in self._custom_emojis(interaction.guild, len(self._blocks(plan))):
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
        start="First slot number (inclusive)",
        end="Last slot number (inclusive)",
        id="Optional plan ID shown on the card",
    )
    async def schedule(
        self, interaction: discord.Interaction, start: int, end: int, id: str | None = None
    ) -> None:
        if not await self._require_planning_channel(interaction):
            return
        plan = self.service.find_open(plan_id=id, leader_id=interaction.user.id)
        if plan is None:
            await interaction.response.send_message(
                "I could not find an open planning poll for that ID.", ephemeral=True
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
            blocks = self._blocks(plan)
            start_index, end_index = schedule_slot_indices(plan, start, end)
            scheduled_start, scheduled_end = blocks[start_index].start, blocks[end_index - 1].end
        except ValueError as exc:
            await interaction.response.send_message(
                str(exc),
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
            recipients = overlapping_users(plan, start_index, end_index)
            channel = self.bot.get_channel(plan.channel_id)
            message = await channel.fetch_message(plan.message_id) if channel else None
            if message:
                updated_plan = replace(
                    plan, scheduled_start=scheduled_start, scheduled_end=scheduled_end
                )
                await message.edit(embed=self._embed(updated_plan))
                plan.scheduled_start, plan.scheduled_end = scheduled_start, scheduled_end
            else:
                await interaction.response.send_message(
                    "I could not fetch the planning card.", ephemeral=True
                )
                return
            await interaction.response.send_message(
                f"Scheduled **{plan.name}** (`{plan.id}`), slots {start}–{end}, and notifying {len(recipients)} available member(s).",
                ephemeral=True,
            )
            for user_id, selected in recipients.items():
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    await user.send(
                        embed=self._scheduled_notification_embed(
                            plan,
                            selected=selected,
                            blocks=blocks,
                            start_index=start_index,
                            end_index=end_index,
                            guild_name=(
                                interaction.guild.name if interaction.guild else "This server"
                            ),
                            jump_url=message.jump_url,
                        ),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    continue

    @plan.command(name="cancel", description="Close a planning poll without scheduling it")
    @app_commands.describe(id="Optional plan ID shown on the card")
    async def cancel(self, interaction: discord.Interaction, id: str | None = None) -> None:
        if not await self._require_planning_channel(interaction):
            return
        plan = self.service.find_open(plan_id=id, leader_id=interaction.user.id)
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
        lock = self._locks.setdefault(plan.message_id, asyncio.Lock())
        async with lock:
            if not plan.is_open:
                await interaction.response.send_message(
                    "This planning poll is already closed.", ephemeral=True
                )
                return
            channel = self.bot.get_channel(plan.channel_id)
            message = await channel.fetch_message(plan.message_id) if channel else None
            if message is None:
                await interaction.response.send_message(
                    "I could not fetch the planning card.", ephemeral=True
                )
                return
            updated_plan = replace(plan, cancelled=True)
            await message.edit(embed=self._embed(updated_plan))
            plan.cancelled = True
        await interaction.response.send_message(
            f"Planning poll **{plan.name}** (`{plan.id}`) cancelled.", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user) -> None:
        await self._record_reaction(reaction, user, added=True)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user) -> None:
        await self._record_reaction(reaction, user, added=False)

    async def _record_reaction(self, reaction, user, *, added: bool) -> None:
        if user.bot:
            return
        index = self._reaction_index(reaction.emoji)
        if index is None:
            return
        if not self.service.update_reaction(reaction.message.id, user.id, index, added):
            return
        plan = self.service.plans[reaction.message.id]
        await reaction.message.edit(embed=self._embed(plan))

    @staticmethod
    def _reaction_index(emoji) -> int | None:
        name = getattr(emoji, "name", None)
        if name and name.isdigit() and 1 <= int(name) <= MAX_PLAN_BLOCKS:
            return int(name) - 1
        try:
            return NUMBER_EMOJIS.index(str(emoji))
        except ValueError:
            return None

    @staticmethod
    def _custom_emojis(guild, count: int):
        emojis = {emoji.name: emoji for emoji in guild.emojis}
        missing = [str(index) for index in range(1, count + 1) if str(index) not in emojis]
        if missing:
            raise ValueError("This server needs custom emojis named " + ", ".join(missing) + ".")
        return [emojis[str(index)] for index in range(1, count + 1)]

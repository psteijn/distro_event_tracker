import asyncio
import csv
import inspect
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Union

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from .config import (
    ADMIN_IDS,
    BOT_PREFIX,
    DIBS_CHANNEL_ID,
    DISCORD_TOKEN,
    EMOJI_FIFTY,
    EMOJI_HUNDRED,
    EMOJI_SEVENTY_FIVE,
    EMOJI_TWENTY_FIVE,
    EVENT_CHANNEL_ID,
    EVENT_COMMAND_NAME,
    ITEMS_CSV,
    REMINDER_OPT_OUT_FILE,
)
from .events.models import Event
from .events.reminders import handle_event_reminder
from .events.scoring import calculate_event_weighted_scores as calculate_domain_event_scores
from .events.service import EventService

# Logging configuration
log_file = os.getenv('LOG_FILE', 'bot.log')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger('bot')

# Ensure stdout supports UTF-8 for printing emojis to console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Pacific timezone (handles daylight savings automatically)
PACIFIC_TZ = pytz.timezone('US/Pacific')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True


class EventBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        from .bootstrap import install_cogs

        await install_cogs(
            self,
            sys.modules[__name__],
            DIBS_CHANNEL_ID,
            EVENT_COMMAND_NAME,
            EVENT_CHANNEL_ID,
        )

        # Sync the tree globally to make slash commands appear everywhere
        try:
            # Syncing with guild=None (default) makes commands global
            synced = await self.tree.sync()
            logger.info(f"✅ Successfully synchronized {len(synced)} global slash commands.")
            for command in synced:
                logger.info(f"   - /{command.name}")
        except Exception as e:
            logger.error(f"❌ Failed to synchronize slash commands: {e}")


bot = EventBot(command_prefix=BOT_PREFIX, intents=intents, case_insensitive=True)


def register_dibs_tree_command(*args, **kwargs):
    """Register a slash command only when the dibs channel is configured."""

    def decorator(func):
        if DIBS_CHANNEL_ID:
            return bot.tree.command(*args, **kwargs)(func)
        return func

    return decorator


def _count_total_dibs_entries() -> int:
    return sum(len(user_dibs) for user_dibs in dibs_tracker.dibs.values())


async def refresh_dibs_summary(
    guild,
    *,
    reason: Optional[str] = None,
    actor: Optional[str] = None,
    actor_name: Optional[str] = None,
    details: Optional[dict] = None,
):
    """Refreshes the dibs summary message in the designated channel."""
    caller_frame = inspect.stack()[1]
    caller = (
        f"{os.path.basename(caller_frame.filename)}:{caller_frame.function}:{caller_frame.lineno}"
    )
    refresh_reason = reason or "unspecified"
    logger.info(
        "DIBS SUMMARY REFRESH START reason=%s actor=%s actor_name=%s caller=%s state=%s details=%s",
        refresh_reason,
        actor or "unknown",
        actor_name or "unknown",
        caller,
        {"users": len(dibs_tracker.dibs), "entries": _count_total_dibs_entries()},
        details or {},
    )
    if not DIBS_CHANNEL_ID:
        logger.info("DIBS SUMMARY REFRESH SKIPPED reason=no_dibs_channel_configured")
        return

    channel = bot.get_channel(int(DIBS_CHANNEL_ID))
    if not channel:
        logger.error(
            "DIBS SUMMARY REFRESH FAILED reason=channel_not_found dibs_channel_id=%s",
            DIBS_CHANNEL_ID,
        )
        return

    # Delete old summary and data messages
    deleted_summary_messages = 0
    deleted_data_messages = 0
    try:
        async for message in channel.history(limit=50):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                is_summary = embed.title == "📦 Current Dibs Summary"
                is_data = False
                if (
                    embed.footer
                    and getattr(embed.footer, 'icon_url', None)
                    and "https://dibs.data?payload=" in embed.footer.icon_url
                ):
                    is_data = True
                if embed.description and "http://dibs.data?payload=" in embed.description:
                    is_data = True
                if embed.title == "⚙️ Dibs System Data (DO NOT DELETE)":
                    is_data = True
                if embed.footer and embed.footer.text and embed.footer.text.startswith("DATA:"):
                    is_data = True

                if is_summary or is_data:
                    await message.delete()
                    if is_summary:
                        deleted_summary_messages += 1
                    if is_data:
                        deleted_data_messages += 1
    except Exception as e:
        logger.error(f"❌ Error deleting old dibs summary: {e}")

    # 1. Send the Data Message(s) (Machine readable persistence)
    # We split the dibs state into multiple chunks to stay safely under Discord's 2,048 character footer icon_url limit.
    import json
    import urllib.parse

    chunks = []
    current_chunk = {}
    for uid, user_dibs in dibs_tracker.dibs.items():
        test_chunk = current_chunk.copy()
        test_chunk[str(uid)] = user_dibs
        test_json = json.dumps(test_chunk)
        # 800 characters allows room for URL encoding expansion
        if len(test_json) > 800:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = {str(uid): user_dibs}
        else:
            current_chunk[str(uid)] = user_dibs

    if current_chunk or not chunks:
        chunks.append(current_chunk)

    logger.info(
        "DIBS SUMMARY REFRESH REBUILD reason=%s channel_id=%s deleted_summary_messages=%s deleted_data_messages=%s data_chunks=%s",
        refresh_reason,
        channel.id,
        deleted_summary_messages,
        deleted_data_messages,
        len(chunks),
    )

    for i, chunk in enumerate(chunks):
        chunk_json = json.dumps(chunk)
        encoded_data = urllib.parse.quote(chunk_json)

        title_str = (
            "⚙️ System Data Block"
            if len(chunks) == 1
            else f"⚙️ System Data Block ({i+1}/{len(chunks)})"
        )
        data_embed = discord.Embed(
            title=title_str,
            description="This message is used for tracking bot state. **Do not delete or modify.**",
            color=0x2B2D31,  # Matches Discord Dark Mode background
        )
        data_embed.set_footer(
            text="⚙️ System Metadata (Ignore)", icon_url=f"https://dibs.data?payload={encoded_data}"
        )
        await channel.send(embed=data_embed)

    # 2. Send the Summary Message (Human readable view)
    summary_embed = discord.Embed(
        title="📦 Current Dibs Summary",
        description="Here is the list of current dibs for all players.",
        color=discord.Color.gold(),
    )

    if not dibs_tracker.dibs:
        summary_embed.description = "No active dibs."
    else:
        # Build a map of item_name -> list of (user_id, qty)
        item_to_users = {}
        for user_id, user_dibs in dibs_tracker.dibs.items():
            for item, qty in user_dibs.items():
                if item not in item_to_users:
                    item_to_users[item] = []
                item_to_users[item].append((user_id, qty))

        # Build list lines
        lines = []
        for item in sorted(item_to_users.keys()):
            claims = []
            for user_id, qty in item_to_users[item]:
                qty_str = str(qty) if qty else "Any"
                claims.append(f"<@{user_id}> ({qty_str})")

            claims_str = ", ".join(claims)
            lines.append(f"**{DibsTracker.display_dib_item_name(item)}** | {claims_str}")

        summary_embed.description = "\n".join(lines)

    summary_embed.timestamp = datetime.now(PACIFIC_TZ)
    await channel.send(embed=summary_embed)
    logger.info(
        "DIBS SUMMARY REFRESH COMPLETE reason=%s channel_id=%s users=%s entries=%s",
        refresh_reason,
        channel.id,
        len(dibs_tracker.dibs),
        _count_total_dibs_entries(),
    )


async def item_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete for the /dibs command"""
    items = dibs_tracker.all_items
    return [
        app_commands.Choice(name=item, value=item)
        for item in items
        if current.lower() in item.lower()
    ][:25]


def resolve_dibs_item_name(item: str) -> Optional[str]:
    """Resolve a dibs item name using exact or unique fuzzy matching."""
    normalized_item = " ".join(item.split()).lower()
    if not normalized_item:
        return None

    exact_matches = [
        candidate for candidate in dibs_tracker.all_items if candidate.lower() == normalized_item
    ]
    if exact_matches:
        return exact_matches[0]

    fuzzy_matches = [
        candidate for candidate in dibs_tracker.all_items if normalized_item in candidate.lower()
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]

    return None


async def undibs_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete for the /undibs command (all items, but prioritizes user's dibs)"""
    user_id = interaction.user.id
    choices = [app_commands.Choice(name="[ALL] Clear all dibs", value="all")]

    # 1. Add active dibs for this user first
    active_items = []
    if user_id in dibs_tracker.dibs:
        active_items = list(dibs_tracker.dibs[user_id].keys())
        for item in active_items:
            if current.lower() in item.lower():
                choices.append(app_commands.Choice(name=f"📌 {item}", value=item))

    # 2. Add the rest of the items from the CSV if we have space
    if len(choices) < 25:
        for item in dibs_tracker.all_items:
            if item not in active_items and current.lower() in item.lower():
                choices.append(app_commands.Choice(name=item, value=item))
                if len(choices) >= 25:
                    break

    return choices[:25]


@register_dibs_tree_command(
    name="dibs", description="Claim dibs on an item from the distribution list"
)
@app_commands.describe(item="The item you want to claim", quantity="Optional number of items")
@app_commands.autocomplete(item=item_autocomplete)
async def dibs(interaction: discord.Interaction, item: str, quantity: Optional[int] = None):
    """Slash command to claim dibs"""
    if DIBS_CHANNEL_ID and str(interaction.channel_id) != DIBS_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ This command can only be used in the designated dibs channel.", ephemeral=True
        )
        return

    # Validate item
    resolved_item = resolve_dibs_item_name(item)
    if resolved_item:
        item = resolved_item
    else:
        await interaction.response.send_message(
            f"❌ '{item}' is not a recognized item. Please use the autocomplete suggestions.",
            ephemeral=True,
        )
        return

    # Process quantity
    try:
        qty_val = normalize_dibs_quantity(quantity)
    except ValueError as exc:
        await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        return

    dibs_tracker.add_dib(interaction.user.id, item, qty_val)
    await interaction.response.send_message(
        f"✅ Dibs registered: **{item}** (Quantity: {qty_val})", ephemeral=True
    )

    # Refresh the summary
    await refresh_dibs_summary(
        interaction.guild,
        reason="dibs_command",
        actor=str(interaction.user.id),
        actor_name=interaction.user.name,
        details={"item": item, "quantity": qty_val},
    )
    logger.info(f"DIBS: {interaction.user.name} added {item} ({qty_val})")


@register_dibs_tree_command(
    name="custom_dibs", description="Claim a custom dibs entry using free-form text"
)
@app_commands.describe(text="The custom dibs text", quantity="Optional number of items")
async def custom_dibs(interaction: discord.Interaction, text: str, quantity: Optional[int] = None):
    """Slash command to claim a custom dibs entry."""
    if DIBS_CHANNEL_ID and str(interaction.channel_id) != DIBS_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ This command can only be used in the designated dibs channel.", ephemeral=True
        )
        return

    item_text = " ".join(text.split()).strip()
    if not item_text:
        await interaction.response.send_message(
            "❌ Please provide some text for your custom dibs entry.", ephemeral=True
        )
        return

    try:
        qty_val = normalize_dibs_quantity(quantity)
    except ValueError as exc:
        await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        return

    dibs_tracker.add_custom_dib(interaction.user.id, item_text, qty_val)
    await interaction.response.send_message(
        f"✅ Custom dibs registered: **{item_text}** (Quantity: {qty_val})",
        ephemeral=True,
    )

    await refresh_dibs_summary(
        interaction.guild,
        reason="custom_dibs_command",
        actor=str(interaction.user.id),
        actor_name=interaction.user.name,
        details={"text": item_text, "quantity": qty_val},
    )
    logger.info(f"CUSTOM DIBS: {interaction.user.name} added {item_text} ({qty_val})")


@register_dibs_tree_command(name="undibs", description="Remove one or all of your dibs")
@app_commands.describe(item="The item to remove, or 'all' to clear all")
@app_commands.autocomplete(item=undibs_autocomplete)
async def undibs(interaction: discord.Interaction, item: str):
    """Slash command to remove dibs"""
    if DIBS_CHANNEL_ID and str(interaction.channel_id) != DIBS_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ This command can only be used in the designated dibs channel.", ephemeral=True
        )
        return

    user_id = interaction.user.id

    if item.lower() == "all":
        if dibs_tracker.remove_all_dibs(user_id):
            await interaction.response.send_message(
                "✅ All your dibs have been cleared.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ You have no active dibs to clear.", ephemeral=True
            )
    else:
        target_item = dibs_tracker.resolve_user_dib_key(user_id, item)
        if not target_item:
            await interaction.response.send_message(
                f"❌ You don't have dibs on '{item}'.", ephemeral=True
            )
            return

        display_item = dibs_tracker.display_dib_item_name(target_item)

        if dibs_tracker.remove_dib(user_id, target_item):
            await interaction.response.send_message(
                f"✅ Removed dibs on: **{display_item}**", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to remove dibs on '{display_item}'.", ephemeral=True
            )

    # Refresh the summary
    await refresh_dibs_summary(
        interaction.guild,
        reason="undibs_command",
        actor=str(interaction.user.id),
        actor_name=interaction.user.name,
        details={"item": item},
    )
    logger.info(f"UNDIBS: {interaction.user.name} removed {item}")


# In-memory storage for events (will be replaced with database later)
events_storage = {}

# Global emoji cache - loaded once at startup
hundred_emoji = None
seventy_five_emoji = None
fifty_emoji = None
twenty_five_emoji = None


# Event type mapping for raw data output
EVENT_TYPE_MAP = {"🏰": "dungeon", "⚔️": "mini", "🗺️": "t8", "👹": "main", "👑": "omni"}


# Mapping for backfill command
BACKFILL_TYPE_MAP = {
    "dungeon": ("🏰", 1.0, discord.Color.blue()),
    "mini": ("⚔️", 1.0, discord.Color.orange()),
    "miniboss": ("⚔️", 1.0, discord.Color.orange()),
    "boss": ("👹", 2.0, discord.Color.red()),
    "main": ("👹", 2.0, discord.Color.red()),
    "mainboss": ("👹", 2.0, discord.Color.red()),
    "t8": ("🗺️", 1.0, discord.Color.green()),
    "omni": ("👑", 8.0, discord.Color.purple()),
    "omniboss": ("👑", 8.0, discord.Color.purple()),
}


async def send_long_message(ctx, content: Union[str, List[str]], code_block: bool = True):
    """
    Sends long content by splitting it into chunks of up to 2000 characters.
    If 'content' is a list, it treats each item as an unbreakable block (whenever possible)
    to ensure splits happen between entire events/records.
    """
    if not content:
        return

    # Discord limit is 2000, but we use a smaller limit to account for code blocks (```\n...\n```)
    limit = 1900

    # Convert single string to list of lines if needed
    if isinstance(content, str):
        blocks = content.split('\n')
    else:
        blocks = content

    current_chunk = ""

    for block in blocks:
        # If adding this block (plus a newline) would exceed the limit
        if len(current_chunk) + len(block) + 1 > limit:
            # If current_chunk is not empty, send it
            if current_chunk:
                msg_content = f"```\n{current_chunk}\n```" if code_block else current_chunk
                await ctx.send(msg_content)
                current_chunk = ""

            # If the single block is still too long, we MUST split it
            if len(block) > limit:
                # For blocks > limit, we attempt to split at comma to be helpful
                parts = block.split(', ')
                for part in parts:
                    if len(current_chunk) + len(part) + 2 > limit:
                        if current_chunk:
                            msg_content = (
                                f"```\n{current_chunk}\n```" if code_block else current_chunk
                            )
                            await ctx.send(msg_content)
                            current_chunk = ""

                        # Hard chop extreme case (if even a single part is > limit)
                        if len(part) > limit:
                            for i in range(0, len(part), limit):
                                sub_part = part[i : i + limit]
                                await ctx.send(f"```\n{sub_part}\n```" if code_block else sub_part)
                            continue

                        current_chunk = part
                    else:
                        if current_chunk:
                            current_chunk += ", " + part
                        else:
                            current_chunk = part

                # After processing long block parts, send whatever is left
                if current_chunk:
                    msg_content = f"```\n{current_chunk}\n```" if code_block else current_chunk
                    await ctx.send(msg_content)
                    current_chunk = ""
                continue

        # Normal block processing
        if current_chunk:
            current_chunk += "\n" + block
        else:
            current_chunk = block

    # Send final chunk
    if current_chunk:
        msg_content = f"```\n{current_chunk}\n```" if code_block else current_chunk
        await ctx.send(msg_content)


def generate_single_event_summary(event: Dict) -> discord.Embed:
    """Generate a detailed summary embed for a single event"""
    embed = discord.Embed(title=f"📊 Event Summary: {event['name']}", color=discord.Color.blue())

    # Add event details
    embed.add_field(name="Event ID", value=event['id'], inline=True)

    # Format creation time
    created_time = datetime.fromtimestamp(event['created_at'], tz=PACIFIC_TZ)
    created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')

    embed.add_field(name="Created", value=created_time_str, inline=True)

    # Get creator name
    creator_name = "Unknown"
    try:
        # Try to get the creator from the bot's user cache
        creator = bot.get_user(event['creator_id'])
        if creator:
            creator_name = creator.name
    except Exception:
        pass

    embed.add_field(name="Created by", value=creator_name, inline=True)

    # Process attendance
    total_attendees = len(event['attendance']) + len(event.get('manual_attendance', []))
    embed.add_field(name="Total Attendees", value=str(total_attendees), inline=True)

    # Add attendance breakdown
    if event['attendance'] or event.get('manual_attendance'):
        attendance_text = []

        # Regular attendance (from reactions)
        for user_id, (user_name, emojis) in event['attendance'].items():
            emoji_text = " ".join(emojis) if emojis else "❓"
            attendance_text.append(f"{emoji_text} {user_name}")

        # Manual attendance
        for user_data in event.get('manual_attendance', []):
            if isinstance(user_data, dict):
                emoji_text = multiplier_to_emoji_string(user_data['multiplier'])
                attendance_text.append(f"{emoji_text} {user_data['name']}")
            else:
                attendance_text.append(f"✅ {str(user_data)}")

        # Split into chunks if too long
        if len(attendance_text) > 20:
            # Split into multiple fields
            chunks = [attendance_text[i : i + 20] for i in range(0, len(attendance_text), 20)]
            for i, chunk in enumerate(chunks):
                field_name = f"Attendees (Part {i+1})" if len(chunks) > 1 else "Attendees"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
        else:
            embed.add_field(name="Attendees", value="\n".join(attendance_text), inline=False)
    else:
        embed.add_field(name="Attendees", value="No attendees yet", inline=False)

    # Add weighted score calculation
    if event['attendance'] or event.get('manual_attendance'):
        weighted_scores = calculate_event_weighted_scores(event)
        if weighted_scores:
            score_text = []
            for user_name, score in weighted_scores.items():
                score_str = f"{score:.2f}".rstrip('0').rstrip('.')
                score_text.append(f"{user_name}: {score_str}")

            embed.add_field(name="Weighted Scores", value="\n".join(score_text), inline=False)

    embed.set_footer(text=f"Event ID: {event['id']}")
    embed.timestamp = datetime.now(PACIFIC_TZ)

    return embed


def update_embed_manual_attendance(
    embed: discord.Embed, manual_attendance: List[Dict]
) -> discord.Embed:
    """Shared helper to update the Manual Attendance field in an event embed"""
    if not manual_attendance:
        return embed

    # Create the manual attendance display string with emojis
    manual_attendance_display = []
    for user_data in manual_attendance:
        if isinstance(user_data, dict):
            # New format with emoji based on multiplier
            emoji_string = multiplier_to_emoji_string(user_data['multiplier'])
            manual_attendance_display.append(f"{emoji_string} {user_data['name']}")
        else:
            # Old format safety check
            manual_attendance_display.append(str(user_data))

    field_value = ', '.join(manual_attendance_display)

    # Truncate if it exceeds Discord's field limit (1024 chars)
    if len(field_value) > 1024:
        field_value = field_value[:1021] + "..."

    found_existing_field = False
    for index, field in enumerate(embed.fields):
        if field.name == "Manual Attendance":
            # Replace the field with updated manual attendance
            embed.set_field_at(
                index,
                name=field.name,
                value=field_value,
                inline=field.inline,
            )
            found_existing_field = True
            break

    if not found_existing_field:
        embed.add_field(
            name="Manual Attendance",
            value=field_value,
            inline=True,
        )

    return embed


def calculate_event_weighted_scores(event: Dict) -> Dict[str, float]:
    """Calculate weighted scores for attendees of a single event"""
    return calculate_domain_event_scores(event)

    # Compatibility implementation retained temporarily for easy wire-format auditing.
    user_scores = {}
    event_multiplier = event.get('multiplier', 1.0)

    # Process regular attendance
    for user_id, (user_name, emojis) in event['attendance'].items():
        participation_multiplier = 0.0
        for emoji in emojis:
            # Extract emoji name from Discord emoji string
            emoji_name = None
            if emoji.startswith('<:') and emoji.endswith('>'):
                emoji_name = emoji.split(':')[1]
            else:
                emoji_name = emoji

            # Determine participation multiplier based on emoji
            if emoji_name == EMOJI_HUNDRED:
                participation_multiplier = max(participation_multiplier, 1.0)
            elif emoji_name == EMOJI_SEVENTY_FIVE:
                participation_multiplier = max(participation_multiplier, 0.75)
            elif emoji_name == EMOJI_FIFTY:
                participation_multiplier = max(participation_multiplier, 0.5)
            elif emoji_name == EMOJI_TWENTY_FIVE:
                participation_multiplier = max(participation_multiplier, 0.25)

        user_scores[user_name] = event_multiplier * participation_multiplier

    # Process manual attendance
    for user_data in event.get('manual_attendance', []):
        if isinstance(user_data, dict):
            user_name = user_data['name']
            user_multiplier = user_data['multiplier']
            user_scores[user_name] = event_multiplier * user_multiplier

    # Sort by score (descending)
    return dict(sorted(user_scores.items(), key=lambda x: x[1], reverse=True))


def generate_single_event_text_summary(event: Dict) -> str:
    """Generate a text summary for a single event in the same format as the summary command"""
    # Format creation time
    created_time = datetime.fromtimestamp(event['created_at'], tz=PACIFIC_TZ)
    created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')

    # Start building the text output
    text_output = "📊 Event Attendance Summary\n"
    text_output += f"Event: {event['name']}\n"
    text_output += f"Created: {created_time_str}\n"
    text_output += (
        f"Total Attendees: {len(event['attendance']) + len(event.get('manual_attendance', []))}\n\n"
    )

    # Build attendance list (same format as summary command)
    attendees_list = []

    # Regular attendance (from reactions)
    for user_id, (user_name, emojis) in event['attendance'].items():
        attendees_list.append(user_name)

    # Manual attendance
    for user_data in event.get('manual_attendance', []):
        if isinstance(user_data, dict):
            attendees_list.append(user_data['name'])
        else:
            attendees_list.append(str(user_data))

    # Add attendance line
    if attendees_list:
        text_output += f"{event['name']}: {', '.join(attendees_list)}\n"
    else:
        text_output += f"{event['name']}: (no attendees)\n"

    # Add event name line
    text_output += f"\n-------\nEvents: {event['name']}\n"

    # Add weighted average summary for this single event
    weighted_scores = calculate_event_weighted_scores(event)
    if weighted_scores:
        score_summary = []
        for user_name, score in weighted_scores.items():
            score_str = f"{score:.2f}".rstrip('0').rstrip('.')
            score_summary.append(f"{user_name} ({score_str})")
        text_output += f"ALL EVENTS: {', '.join(score_summary)}\n"
    else:
        text_output += "ALL EVENTS: No attendees found\n"

    return text_output


class EventTracker:
    def __init__(self, opt_out_file: str = "reminders_opt_out.txt"):
        self.service = EventService()
        self.events = self.service.events
        self.opt_out_file = opt_out_file
        self.opted_out_users = set()
        self.load_opt_out_preferences()

    def load_opt_out_preferences(self):
        """Load opted-out users from the local file"""
        if os.path.exists(self.opt_out_file):
            try:
                with open(self.opt_out_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.opted_out_users.add(int(line))
                logger.info(
                    f"✅ Loaded {len(self.opted_out_users)} opted-out users from {self.opt_out_file}"
                )
            except Exception as e:
                logger.error(f"❌ Error loading opt-out preferences: {e}")
        else:
            logger.info(f"ℹ️ No opt-out file found at {self.opt_out_file}. Starting fresh.")

    def save_opt_out_preferences(self):
        """Save opted-out users to the local file"""
        try:
            with open(self.opt_out_file, 'w') as f:
                for user_id in sorted(self.opted_out_users):
                    f.write(f"{user_id}\n")
            logger.info(f"💾 Saved opt-out preferences to {self.opt_out_file}")
        except Exception as e:
            logger.error(f"❌ Error saving opt-out preferences: {e}")

    def toggle_reminders(self, user_id: int, status: bool) -> bool:
        """Toggle reminder preference for a user. True = ON, False = OFF"""
        if status:
            # Opt back in
            if user_id in self.opted_out_users:
                self.opted_out_users.remove(user_id)
                self.save_opt_out_preferences()
                return True
        else:
            # Opt out
            if user_id not in self.opted_out_users:
                self.opted_out_users.add(user_id)
                self.save_opt_out_preferences()
                return True
        return False

    def create_event(
        self,
        event_id: str,
        name: str,
        channel_id: int,
        message_id: int,
        creator_id: int,
        created_at: float,
        multiplier: float = 1.0,
        type_emoji: str = "",
        is_historical: bool = False,
    ) -> Dict:
        """Create a new event with a multiplier for scoring"""
        event = Event(
            id=event_id,
            name=name,
            type_emoji=type_emoji,
            channel_id=channel_id,
            message_id=message_id,
            creator_id=creator_id,
            created_at=created_at,
            multiplier=multiplier,
            is_historical=is_historical,
        )
        return self.service.create_event(event)

    def add_attendance(self, event_id: str, user_id: int, user_name: str, emoji: str) -> bool:
        """Add attendance record for a user"""
        return self.service.add_attendance(event_id, user_id, user_name, emoji)

        if event_id in self.events:
            if user_id not in self.events[event_id]['attendance']:
                self.events[event_id]['attendance'][user_id] = (user_name, [])
            if emoji not in self.events[event_id]['attendance'][user_id][1]:
                self.events[event_id]['attendance'][user_id][1].append(emoji)
            return True
        return False

    def remove_attendance(self, event_id: str, user_id: int, user_name: str, emoji: str) -> bool:
        """Remove attendance record for a user"""
        return self.service.remove_attendance(event_id, user_id, emoji)

        if event_id in self.events and user_id in self.events[event_id]['attendance']:
            if emoji in self.events[event_id]['attendance'][user_id][1]:
                self.events[event_id]['attendance'][user_id][1].remove(emoji)
                if not self.events[event_id]['attendance'][user_id][1]:
                    del self.events[event_id]['attendance'][user_id]
            return True
        return False

    def get_events_in_range(self, start_timestamp_sec: int, end_timestamp_sec: int) -> List[Dict]:
        """Get all events within a date range"""
        return self.service.events_in_range(start_timestamp_sec, end_timestamp_sec)

        filtered_events = []
        for event in self.events.values():
            event_timestamp_sec = event['created_at']

            if start_timestamp_sec <= event_timestamp_sec <= end_timestamp_sec:
                filtered_events.append(event)

        # Always return sorted by time
        return sorted(filtered_events, key=lambda x: x['created_at'])

    def get_events_between_ids(self, start_id: str, end_id: str) -> List[Dict]:
        """Get all events between two specific IDs (inclusive)"""
        return self.service.events_between_ids(start_id, end_id)

        # Sort all events chronologically
        all_events = sorted(self.events.values(), key=lambda x: x['created_at'])

        start_idx = -1
        end_idx = -1

        for i, event in enumerate(all_events):
            if event['id'] == start_id:
                start_idx = i
            if event['id'] == end_id:
                end_idx = i

        if start_idx != -1 and end_idx != -1:
            # Ensure range is correct even if IDs were provided out of order
            s, e = min(start_idx, end_idx), max(start_idx, end_idx)
            return all_events[s : e + 1]

        return []

    def get_last_n_events(self, n: int) -> List[Dict]:
        """Get the most recent N events"""
        return self.service.last_events(n)

        all_events = sorted(self.events.values(), key=lambda x: x['created_at'], reverse=True)
        return sorted(all_events[:n], key=lambda x: x['created_at'])

    def get_most_recent_before(self, event_id: str) -> Optional[Dict]:
        """Find the most recent event created before the given event ID"""
        return self.service.most_recent_before(event_id)

        if event_id not in self.events:
            return None

        target_event = self.events[event_id]
        target_time = target_event['created_at']

        # Filter for events before the target and sort by time descending
        events_before = [e for e in self.events.values() if e['created_at'] < target_time]
        if not events_before:
            return None

        sorted_before = sorted(events_before, key=lambda x: x['created_at'], reverse=True)
        return sorted_before[0]

    def generate_summary(self, events: List[Dict]) -> Dict:
        """Generate attendance summary for events"""
        summary = {
            'generated_at': get_pacific_now().isoformat(),
            'total_events': len(events),
            'events': [],
        }

        for event in events:
            # Ensure manual_attendance key exists (defensive coding for existing events)
            if 'manual_attendance' not in event:
                event['manual_attendance'] = []

            # Start from a shallow copy so we don't mutate the original attendance dict
            attendance_by_user = dict(event['attendance'])
            for user_data in event['manual_attendance']:
                user_name = user_data['name']
                user_multiplier = user_data['multiplier']

                if user_name not in attendance_by_user:
                    # Use the appropriate emoji based on multiplier
                    emoji_string = multiplier_to_emoji_string(user_multiplier)
                    attendance_by_user[user_name] = (user_name, [emoji_string])

            event_summary = {
                'id': event['id'],
                'name': event['name'],
                'type_emoji': event.get('type_emoji', ''),
                'multiplier': event['multiplier'],
                'created_at': event['created_at'],
                'total_attendees': len(attendance_by_user),
                'attendance_by_user': attendance_by_user,
            }
            summary['events'].append(event_summary)

        return summary

    def generate_raw_data_summary(self, events: List[Dict]) -> List[str]:
        """Generate raw attendance data for events for the !data command"""
        if not events:
            return ["No events found"]

        event_strings = []
        for event in events:
            # We need the attendance with scores
            weighted_scores = calculate_event_weighted_scores(event)

            # Get event type from emoji
            event_type = EVENT_TYPE_MAP.get(event.get('type_emoji', ''), 'unknown')

            # Format: [event_id] [event_type] Event Name: User1 (score), User2 (score)
            attendees = []
            for user_name, score in weighted_scores.items():
                score_str = f"{score:.2f}".rstrip('0').rstrip('.')
                attendees.append(f"{user_name} ({score_str})")

            line = f"[{event['id']}] [{event_type}] {event['name']}: {', '.join(attendees)}"
            event_strings.append(line)

        return event_strings

    def calculate_weighted_average(self, events: List[Dict]) -> str:
        """Calculate weighted average of attendees across all events"""
        if not events:
            return "No events to analyze"

        # Count attendance for each user across all events with multipliers
        user_attendance_score = {}

        for event in events:
            multiplier = event.get('multiplier', 1.0)  # Default to 1.0 if no multiplier
            for user_id, (user_name, emojis) in event['attendance_by_user'].items():
                participation_multiplier = 0.0
                if user_name not in user_attendance_score:
                    user_attendance_score[user_name] = 0
                for emoji in emojis:
                    # Extract emoji name from Discord emoji string (format: <:name:id> or just the emoji name)
                    emoji_name = None
                    if emoji.startswith('<:') and emoji.endswith('>'):
                        # Custom emoji format: <:share_100:1234567890>
                        emoji_name = emoji.split(':')[1]
                    else:
                        # Unicode emoji or already just the name
                        emoji_name = emoji

                    if emoji_name == EMOJI_HUNDRED:
                        participation_multiplier = 1.0
                    elif emoji_name == EMOJI_SEVENTY_FIVE:
                        participation_multiplier = max(participation_multiplier, 0.75)
                    elif emoji_name == EMOJI_FIFTY:
                        participation_multiplier = max(participation_multiplier, 0.5)
                    elif emoji_name == EMOJI_TWENTY_FIVE:
                        participation_multiplier = max(participation_multiplier, 0.25)

                user_attendance_score[user_name] += multiplier * participation_multiplier

        if not user_attendance_score:
            return "No attendees found"

        # Sort users by attendance score (descending)
        sorted_users = sorted(user_attendance_score.items(), key=lambda x: x[1], reverse=True)

        # Calculate weighted average with multipliers
        weighted_summary = []
        for user_name, score in sorted_users:
            score_str = f"{score:.2f}".rstrip('0').rstrip('.')
            weighted_summary.append(f"{user_name} ({score_str})")

        return f"ALL EVENTS: {', '.join(weighted_summary)}"  # Show all attendees with scores

    async def reconstruct_from_history(self, bot):
        """Reconstruct events from message history with optimizations"""
        logger.info("🔄 Reconstructing events from message history...")
        start_time = asyncio.get_event_loop().time()
        reconstructed_count = 0
        total_messages_scanned = 0
        event_messages_found = 0

        channel = bot.get_channel(int(EVENT_CHANNEL_ID))
        if channel:
            logger.info(f"📖 Scanning channel: {channel.name}")

            # Optimization #1: Early filtering - only process bot messages with embeds
            async for message in channel.history(limit=1000):
                total_messages_scanned += 1

                if total_messages_scanned % 100 == 0:
                    logger.info(
                        f"⏳ Reconstruction progress: Scanned {total_messages_scanned} messages, found {event_messages_found} events so far..."
                    )

                # Early filtering: Skip non-bot messages immediately
                if message.author != bot.user:
                    continue

                # Early filtering: Skip messages without embeds
                if not message.embeds:
                    continue

                event_messages_found += 1

                # Add a small delay between messages to mitigate rate limiting
                await asyncio.sleep(0.1)

                if await self._process_message_for_events(message, is_historical=True):
                    reconstructed_count += 1
        else:
            logger.error(f"❌ Channel {EVENT_CHANNEL_ID} not found")

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        logger.info(
            f"✅ Reconstructed {reconstructed_count} events from {event_messages_found} event messages (scanned {total_messages_scanned} total messages) in {duration:.2f} seconds"
        )
        return reconstructed_count

    async def _process_message_for_events(self, message, is_historical: bool = False):
        """Process a single message to check if it's an event message"""
        # Check if message has embeds (event messages use embeds)
        if not message.embeds:
            return False

        embed = message.embeds[0]

        # Check if this looks like one of the new event types
        if not embed.title:
            return False

        # Detect event type and extract name
        event_name = None
        multiplier = 1.0
        type_emoji = ""

        if embed.title.startswith("🏰 "):
            # Dungeon event
            type_emoji = "🏰"
            event_name = embed.title.replace("🏰 ", "")
            multiplier = 1.0
        elif embed.title.startswith("⚔️ "):
            # Miniboss event
            type_emoji = "⚔️"
            event_name = embed.title.replace("⚔️ ", "")
            multiplier = 1.0
        elif embed.title.startswith("🗺️ "):
            # T8 maps event
            type_emoji = "🗺️"
            event_name = embed.title.replace("🗺️ ", "")
            multiplier = 1.0
        elif embed.title.startswith("👹 "):
            # Boss event
            type_emoji = "👹"
            event_name = embed.title.replace("👹 ", "")
            multiplier = 2.0
        elif embed.title.startswith("👑 "):
            # Omniboss event
            type_emoji = "👑"
            event_name = embed.title.replace("👑 ", "")
            multiplier = 8.0
        else:
            # Not a recognized event type
            return False

        # Extract event ID from footer
        event_id = None
        if embed.footer and embed.footer.text:
            footer_text = embed.footer.text
            if footer_text.startswith("Event ID: "):
                event_id = footer_text.replace("Event ID: ", "")

        if not event_id:
            return False

        # Extract creator info and multiplier from embed fields
        creator_id = None
        embed_multiplier = multiplier  # Default to detected multiplier

        manual_attendance_users = []
        for field in embed.fields:
            if field.name == "Created by":
                # Extract user ID from mention
                creator_mention = field.value
                if creator_mention.startswith("<@") and creator_mention.endswith(">"):
                    creator_id = int(creator_mention[2:-1])
            elif field.name == "Manual Attendance":
                # Extract manual attendance from embed field
                manual_attendance = field.value
                for user_entry in manual_attendance.split(', '):
                    user_entry = user_entry.strip()
                    # Check if this is the new emoji format (e.g., "emoji username")
                    if user_entry.startswith('<:') or user_entry.startswith(':'):
                        # New emoji format - extract username and determine multiplier from emoji
                        parts = user_entry.split(' ', 1)
                        if len(parts) == 2:
                            emoji_str = parts[0]
                            user_name = parts[1]
                            # Determine multiplier from emoji
                            multiplier = 1.0  # Default
                            if emoji_str == str(hundred_emoji) or EMOJI_HUNDRED in emoji_str:
                                multiplier = 1.0
                            elif (
                                emoji_str == str(seventy_five_emoji)
                                or EMOJI_SEVENTY_FIVE in emoji_str
                            ):
                                multiplier = 0.75
                            elif emoji_str == str(fifty_emoji) or EMOJI_FIFTY in emoji_str:
                                multiplier = 0.5
                            elif (
                                emoji_str == str(twenty_five_emoji)
                                or EMOJI_TWENTY_FIVE in emoji_str
                            ):
                                multiplier = 0.25
                            manual_attendance_users.append(
                                {'name': user_name, 'multiplier': multiplier}
                            )
                        else:
                            # Fallback if parsing fails
                            manual_attendance_users.append({'name': user_entry, 'multiplier': 1.0})
                    else:
                        # Old format (just username)
                        manual_attendance_users.append({'name': user_entry, 'multiplier': 1.0})

        # If we can't find creator info, skip this event
        if not creator_id:
            return False

        # Extract timestamp from event_id (format: message_id_timestamp)
        created_at_timestamp = message.created_at.timestamp()

        # Create event entry
        event = {
            'id': event_id,
            'name': event_name,
            'type_emoji': type_emoji,
            'channel_id': message.channel.id,
            'message_id': message.id,
            'creator_id': creator_id,
            'created_at': created_at_timestamp,
            'multiplier': embed_multiplier,
            'attendance': {},
            'manual_attendance': manual_attendance_users,
            'is_historical': is_historical,
        }

        # Process reactions to get attendance
        await self._process_reactions_for_event(event, message)

        # Store the event
        self.events[event_id] = event
        attendance_user_list = [
            user[0] for user in event['attendance'].values()
        ] + manual_attendance_users
        logger.info(
            f"📝 Reconstructed event: {event_name} (ID: {event_id}, multiplier: {embed_multiplier}x, attendance: {attendance_user_list})"
        )
        return True

    async def _process_reactions_for_event(self, event, message):
        """Process reactions on a message to reconstruct attendance with parallel processing"""
        try:
            # Optimization #2: Parallel reaction processing
            # Collect all reaction tasks first
            reaction_tasks = []

            # Only process participation emojis
            valid_emojis = {EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_FIFTY, EMOJI_TWENTY_FIVE}

            for reaction in message.reactions:
                emoji_str = str(reaction.emoji)

                # Extract emoji name if it's a custom emoji
                emoji_name = None
                if emoji_str.startswith('<:') and emoji_str.endswith('>'):
                    emoji_name = emoji_str.split(':')[1]
                else:
                    emoji_name = emoji_str

                if emoji_name in valid_emojis:
                    # Create a task to fetch all users for this reaction
                    task = self._fetch_reaction_users(reaction, emoji_str)
                    reaction_tasks.append(task)

            # Execute all reaction fetching in parallel
            if reaction_tasks:
                reaction_results = await asyncio.gather(*reaction_tasks, return_exceptions=True)

                # Process results
                for result in reaction_results:
                    if isinstance(result, Exception):
                        logger.warning(f"⚠️ Error fetching reaction users: {result}")
                        continue

                    emoji_str, users = result
                    for user in users:
                        if user.bot:
                            continue  # Skip bot reactions

                        # Add attendance record
                        if user.id not in event['attendance']:
                            event['attendance'][user.id] = (user.name, [])

                        if emoji_str not in event['attendance'][user.id][1]:
                            event['attendance'][user.id][1].append(emoji_str)

        except Exception as e:
            logger.error(f"⚠️ Error processing reactions for event {event['name']}: {e}")

    async def _fetch_reaction_users(self, reaction, emoji_str):
        """Helper method to fetch all users for a reaction"""
        try:
            users = []
            async for user in reaction.users():
                users.append(user)
            return (emoji_str, users)
        except Exception as e:
            logger.warning(f"⚠️ Error fetching users for reaction {emoji_str}: {e}")
            return (emoji_str, [])

    async def get_attendance_from_reactions(self, message) -> List[Dict]:
        """Fetch reactions from a message and return them as manual attendance records"""
        imported = []
        # Map emoji names to multipliers
        valid_emojis = {
            EMOJI_HUNDRED: 1.0,
            EMOJI_SEVENTY_FIVE: 0.75,
            EMOJI_FIFTY: 0.5,
            EMOJI_TWENTY_FIVE: 0.25,
        }

        # Parallel fetch similar to _process_reactions_for_event
        tasks = []
        for reaction in message.reactions:
            emoji_str = str(reaction.emoji)

            # Extract emoji name if it's a custom emoji
            emoji_name = None
            if emoji_str.startswith('<:') and emoji_str.endswith('>'):
                emoji_name = emoji_str.split(':')[1]
            else:
                emoji_name = emoji_str

            if emoji_name in valid_emojis:
                tasks.append(self._fetch_reaction_users(reaction, emoji_name))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    continue

                emoji_name, users = result
                # Get the name again because _fetch_reaction_users returns the full emoji_str
                actual_name = (
                    emoji_name.split(':')[1] if emoji_name.startswith('<:') else emoji_name
                )
                mult = valid_emojis.get(actual_name, 1.0)

                for user in users:
                    if user.bot:
                        continue

                    # Add to imported list, avoiding duplicates (keep highest multiplier)
                    existing = next((item for item in imported if item['name'] == user.name), None)
                    if existing:
                        existing['multiplier'] = max(existing['multiplier'], mult)
                    else:
                        imported.append({'name': user.name, 'multiplier': mult})
        return imported


# Initialize event tracker
event_tracker = EventTracker(opt_out_file=REMINDER_OPT_OUT_FILE)


class DibsTracker:
    def __init__(self, items_csv: str = "items.csv"):
        self.dibs = {}  # {user_id: {item_name: quantity}}
        self.items_csv = items_csv
        self.all_items = self.load_items_from_csv()

    def load_items_from_csv(self) -> List[str]:
        """Load valid items from headerless CSV file"""
        items = []
        if os.path.exists(self.items_csv):
            try:
                with open(self.items_csv, mode="r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        for item in row:
                            if item.strip():
                                items.append(item.strip())
                logger.info(f"✅ Loaded {len(items)} items from {self.items_csv}")
            except Exception as e:
                logger.error(f"❌ Error loading items from CSV: {e}")
        else:
            logger.warning(f"⚠️ Items CSV not found at {self.items_csv}")
        return items

    def add_dib(self, user_id: int, item_name: str, quantity: Union[int, str]):
        """Add or update a dib for a user"""
        if user_id not in self.dibs:
            self.dibs[user_id] = {}
        self.dibs[user_id][item_name] = quantity

    def add_custom_dib(self, user_id: int, item_name: str, quantity: Union[int, str]):
        """Add or update a custom dib for a user."""
        self.add_dib(user_id, f"{CUSTOM_DIBS_PREFIX}{item_name}", quantity)

    @staticmethod
    def display_dib_item_name(item_name: str) -> str:
        """Convert a stored dib key into a human-readable label."""
        if item_name.startswith(CUSTOM_DIBS_PREFIX):
            return f"Custom: {item_name[len(CUSTOM_DIBS_PREFIX):]}"
        return item_name

    def resolve_user_dib_key(self, user_id: int, query: str) -> Optional[str]:
        """Resolve a stored dib key from a user-visible query string."""
        if user_id not in self.dibs:
            return None

        normalized_query = " ".join(query.split()).lower()
        if not normalized_query:
            return None

        fuzzy_matches = []
        for stored_item in self.dibs[user_id].keys():
            display_item = self.display_dib_item_name(stored_item).lower()
            stored_item_lower = stored_item.lower()
            if normalized_query == stored_item_lower or normalized_query == display_item:
                return stored_item
            if normalized_query in display_item:
                fuzzy_matches.append(stored_item)
            elif normalized_query in stored_item_lower:
                fuzzy_matches.append(stored_item)

        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]

        return None

    def remove_dib(self, user_id: int, item_name: str) -> bool:
        """Remove a specific dib for a user"""
        stored_item = self.resolve_user_dib_key(user_id, item_name)
        if user_id in self.dibs and stored_item in self.dibs[user_id]:
            del self.dibs[user_id][stored_item]
            if not self.dibs[user_id]:
                del self.dibs[user_id]
            return True
        return False

    def remove_all_dibs(self, user_id: int) -> bool:
        """Remove all dibs for a user"""
        if user_id in self.dibs:
            del self.dibs[user_id]
            return True
        return False

    def get_summary_data(self) -> str:
        """Generate a JSON string of the current dibs state for persistence"""
        return json.dumps(self.dibs)

    def load_from_summary_data(self, data_str: str):
        """Rebuild state from a JSON string"""
        try:
            raw_data = json.loads(data_str)
            # Convert keys back to integers (JSON keys are always strings)
            self.dibs = {int(uid): dibs for uid, dibs in raw_data.items()}
            logger.info(f"✅ Rebuilt dibs state for {len(self.dibs)} users")
        except Exception as e:
            logger.error(f"❌ Error rebuilding dibs from summary data: {e}")

    async def reconstruct_from_history(self, bot):
        """Reconstruct dibs from all system data messages in the dibs channel"""
        if not DIBS_CHANNEL_ID:
            return

        logger.info("🔄 Reconstructing dibs from message history...")
        channel = bot.get_channel(int(DIBS_CHANNEL_ID))
        if not channel:
            logger.error(f"❌ Dibs channel {DIBS_CHANNEL_ID} not found")
            return

        found_any = False
        self.dibs = {}  # Clear local state to rebuild from history

        async for message in channel.history(limit=100):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]

                # 1. Try to find the new icon_url-based data format in the footer
                icon_url = getattr(embed.footer, 'icon_url', None) if embed.footer else None
                if icon_url and "https://dibs.data?payload=" in icon_url:
                    try:
                        import urllib.parse

                        parsed_url = urllib.parse.urlparse(icon_url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        if "payload" in query_params:
                            data_str = query_params["payload"][0]
                            raw_data = json.loads(data_str)
                            for uid, dibs_data in raw_data.items():
                                self.dibs[int(uid)] = dibs_data
                            found_any = True
                    except Exception as e:
                        logger.error(f"❌ Error parsing icon_url-based dibs data: {e}")
                    continue

                # 2. Try to find the description link-based data format
                if embed.description and "http://dibs.data?payload=" in embed.description:
                    try:
                        import urllib.parse

                        start = embed.description.find("http://dibs.data?payload=")
                        end = embed.description.find(")", start)
                        if end != -1:
                            url = embed.description[start:end]
                            parsed_url = urllib.parse.urlparse(url)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            if "payload" in query_params:
                                data_str = query_params["payload"][0]
                                raw_data = json.loads(data_str)
                                for uid, dibs_data in raw_data.items():
                                    self.dibs[int(uid)] = dibs_data
                                found_any = True
                    except Exception as e:
                        logger.error(f"❌ Error parsing link-based dibs data: {e}")
                    continue

                # 3. Fallback: Try the legacy footer-based data format
                if embed.title == "⚙️ Dibs System Data (DO NOT DELETE)" or (
                    embed.footer and embed.footer.text and embed.footer.text.startswith("DATA:")
                ):
                    if embed.footer and embed.footer.text:
                        footer_text = embed.footer.text
                        if footer_text.startswith("DATA:"):
                            try:
                                data_str = footer_text.replace("DATA:", "")
                                raw_data = json.loads(data_str)
                                for uid, dibs_data in raw_data.items():
                                    self.dibs[int(uid)] = dibs_data
                                found_any = True
                            except Exception as e:
                                logger.error(f"❌ Error parsing legacy footer-based dibs data: {e}")

        if found_any:
            logger.info(f"✅ Successfully reconstructed dibs state for {len(self.dibs)} users.")
        else:
            logger.info("ℹ️ No previous dibs system data found. Starting with empty state.")

    def fuzzy_match_item(self, user_id: int, query: str) -> Optional[str]:
        """Find a unique item in user's dibs that matches the query"""
        stored_item = self.resolve_user_dib_key(user_id, query)
        if stored_item:
            return self.display_dib_item_name(stored_item)
        return None


dibs_tracker = DibsTracker(items_csv=ITEMS_CSV)


def normalize_dibs_quantity(quantity: Optional[int]) -> Union[int, str]:
    """Normalize the dibs quantity for storage and display."""
    if quantity is None:
        return "Any"
    if quantity < 1:
        raise ValueError("Quantity must be a positive integer.")
    return quantity


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse various timestamp formats into datetime object in Pacific timezone"""
    timestamp_str = timestamp_str.strip()

    # Remove quotes if present
    if timestamp_str.startswith('"') and timestamp_str.endswith('"'):
        timestamp_str = timestamp_str[1:-1]
    elif timestamp_str.startswith("'") and timestamp_str.endswith("'"):
        timestamp_str = timestamp_str[1:-1]

    # Try epoch timestamp first (numeric)
    if timestamp_str.isdigit():
        try:
            epoch_seconds = int(timestamp_str)
            # Convert epoch to Pacific timezone
            utc_dt = datetime.fromtimestamp(epoch_seconds, tz=pytz.UTC)
            return utc_dt.astimezone(PACIFIC_TZ)
        except (ValueError, OSError):
            pass

    # Try full timestamp format: YYYY-MM-DD HH:MM:SS
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        # Localize to Pacific timezone
        return PACIFIC_TZ.localize(dt)
    except ValueError:
        pass

    # Try date only format: YYYY-MM-DD
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d')
        # Localize to Pacific timezone
        return PACIFIC_TZ.localize(dt)
    except ValueError:
        pass

    # Try alternative formats
    formats = [
        '%Y-%m-%d %H:%M',  # YYYY-MM-DD HH:MM
        '%Y/%m/%d %H:%M:%S',  # YYYY/MM/DD HH:MM:SS
        '%Y/%m/%d %H:%M',  # YYYY/MM/DD HH:MM
        '%Y/%m/%d',  # YYYY/MM/DD
        '%m/%d/%Y %H:%M:%S',  # MM/DD/YYYY HH:MM:SS
        '%m/%d/%Y %H:%M',  # MM/DD/YYYY HH:MM
        '%m/%d/%Y',  # MM/DD/YYYY
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            # Localize to Pacific timezone
            return PACIFIC_TZ.localize(dt)
        except ValueError:
            continue

    raise ValueError(
        f"Unable to parse timestamp: {timestamp_str}. Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, epoch seconds"
    )


def get_pacific_now() -> datetime:
    """Get current time in Pacific timezone"""
    return datetime.now(PACIFIC_TZ)


def multiplier_to_emoji_string(multiplier: float) -> str:
    """Convert a multiplier value to the appropriate emoji string"""
    if multiplier >= 1.0:
        return str(hundred_emoji) if hundred_emoji else EMOJI_HUNDRED
    elif multiplier >= 0.75:
        return str(seventy_five_emoji) if seventy_five_emoji else EMOJI_SEVENTY_FIVE
    elif multiplier >= 0.5:
        return str(fifty_emoji) if fifty_emoji else EMOJI_FIFTY
    elif multiplier >= 0.25:
        return str(twenty_five_emoji) if twenty_five_emoji else EMOJI_TWENTY_FIVE
    else:
        # Default to 25% for very low multipliers
        return str(twenty_five_emoji) if twenty_five_emoji else EMOJI_TWENTY_FIVE


async def resolve_user_name(user_id: int, guild: Optional[discord.Guild] = None) -> str:
    """Resolve a stable username for export and display."""
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.name

    user = bot.get_user(user_id)
    if user:
        return user.name

    try:
        fetched_user = await bot.fetch_user(user_id)
        if fetched_user:
            return fetched_user.name
    except Exception:
        pass

    return f"UnknownUser_{user_id}"


CUSTOM_DIBS_PREFIX = "__custom__:"


@bot.command(name='dibs_data')
async def dibs_data_command(ctx):
    """Generate raw dibs data for export"""
    if (
        DIBS_CHANNEL_ID
        and str(ctx.channel.id) != DIBS_CHANNEL_ID
        and ctx.author.id not in ADMIN_IDS
    ):
        await ctx.send("❌ This command can only be used in the designated dibs channel.")
        return

    if not dibs_tracker.dibs:
        await ctx.send("No active dibs found.")
        return

    output_lines = []
    sorted_user_ids = sorted(dibs_tracker.dibs.keys(), key=lambda uid: str(uid))

    resolved_users = []
    for user_id in sorted_user_ids:
        user_name = await resolve_user_name(user_id, getattr(ctx, "guild", None))
        resolved_users.append((user_name, user_id))

    for user_name, user_id in sorted(resolved_users, key=lambda item: item[0].lower()):
        user_dibs = dibs_tracker.dibs[user_id]

        for item, qty in user_dibs.items():
            qty_str = str(qty) if qty is not None else "Any"
            output_lines.append(
                f"@{user_name}, {dibs_tracker.display_dib_item_name(item)}, {qty_str}"
            )

    await send_long_message(ctx, output_lines, code_block=True)


@bot.event
async def on_ready():
    global hundred_emoji, seventy_five_emoji, fifty_emoji, twenty_five_emoji

    # Start timing initialization
    init_start_time = time.time()

    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')

    # Load emojis once at startup for performance
    try:
        # Get the first guild (assuming bot is only in one guild)
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            hundred_emoji = discord.utils.get(guild.emojis, name=f"{EMOJI_HUNDRED}")
            seventy_five_emoji = discord.utils.get(guild.emojis, name=f"{EMOJI_SEVENTY_FIVE}")
            fifty_emoji = discord.utils.get(guild.emojis, name=f"{EMOJI_FIFTY}")
            twenty_five_emoji = discord.utils.get(guild.emojis, name=f"{EMOJI_TWENTY_FIVE}")

            # Check if all emojis were found
            missing_emojis = []
            if not hundred_emoji:
                missing_emojis.append(EMOJI_HUNDRED)
            if not seventy_five_emoji:
                missing_emojis.append(EMOJI_SEVENTY_FIVE)
            if not fifty_emoji:
                missing_emojis.append(EMOJI_FIFTY)
            if not twenty_five_emoji:
                missing_emojis.append(EMOJI_TWENTY_FIVE)

            if missing_emojis:
                logger.warning(f"⚠️ Warning: Could not find emojis: {', '.join(missing_emojis)}")
            else:
                logger.info(
                    f"✅ Successfully loaded all emojis: {EMOJI_HUNDRED}, {EMOJI_SEVENTY_FIVE}, {EMOJI_FIFTY}, {EMOJI_TWENTY_FIVE}"
                )
        else:
            logger.error("❌ No guilds found - emojis cannot be loaded")
    except Exception as e:
        logger.error(f"❌ Error loading emojis: {e}")

    init_duration = time.time() - init_start_time
    logger.info(
        f"⚡ [Phase 1] Basic initialization complete in {init_duration:.2f}s. Bot is now READY to receive commands."
    )

    # Reconstruct events and dibs from message history
    try:
        recon_start_time = time.time()
        # Run reconstruction in parallel
        results = await asyncio.gather(
            event_tracker.reconstruct_from_history(bot),
            dibs_tracker.reconstruct_from_history(bot),
            return_exceptions=True,
        )

        recon_count = 0
        if not isinstance(results[0], Exception):
            recon_count = results[0]

        if isinstance(results[1], Exception):
            logger.error(f"❌ Error during dibs reconstruction: {results[1]}")

        recon_duration = time.time() - recon_start_time
        total_ready_time = time.time() - init_start_time
        logger.info(
            f'🚀 [Phase 2] Historical reconstruction complete! Processed {recon_count} events in {recon_duration:.2f}s.'
        )
        logger.info(
            f'🏁 Bot fully initialized and memory reconstructed in {total_ready_time:.2f}s.'
        )
    except Exception as e:
        logger.error(f'❌ Error during reconstruction: {e}')
        logger.info('🚀 Bot ready! (Running without historical data)')


@bot.before_invoke
async def before_any_command(ctx):
    """Log every command invocation for better audit trails"""
    logger.info(f"CMD: [{ctx.author}] invoked '{ctx.message.content}' in #{ctx.channel}")


async def create_event_with_multiplier(
    ctx, event_name: str, multiplier: float, emoji: str, color: discord.Color
):
    """Helper function to create events with multipliers"""
    if EVENT_CHANNEL_ID and str(ctx.channel.id) != EVENT_CHANNEL_ID:
        await ctx.send("Events can only be created in the designated event channel.")
        return

    # Check if emojis are loaded
    if not all([hundred_emoji, seventy_five_emoji, fifty_emoji, twenty_five_emoji]):
        await ctx.send("❌ Error: Required emojis are not loaded. Please contact an administrator.")
        logger.error("❌ Error: Attempted to create event but emojis are not loaded")
        return

    # Generate unique event ID
    created_time = ctx.message.created_at.astimezone(PACIFIC_TZ)
    event_id = f"{ctx.message.id}_{int(created_time.timestamp())}"

    # Create event with multiplier
    event = event_tracker.create_event(
        event_id=event_id,
        name=event_name,
        type_emoji=emoji,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id,
        creator_id=ctx.author.id,
        created_at=created_time.timestamp(),
        multiplier=multiplier,
    )

    # Send event message
    embed = discord.Embed(
        title=f"{emoji} {event_name}",
        description=f"React with {hundred_emoji} {seventy_five_emoji} {fifty_emoji} {twenty_five_emoji} to register your attendance!\n{hundred_emoji} is full attendance, the others are partial attendance.",
        color=color,
    )
    embed.add_field(name="Created by", value=ctx.author.mention, inline=True)

    embed.add_field(name="📊Summary", value=f"`!summary {event_id}`", inline=True)
    embed.set_footer(text=f"Event ID: {event_id}")

    event_message = await ctx.send(embed=embed)

    # Update event with the actual message ID
    # NOTE: do this before the reactions below, otherwise fast clicking users can react before these
    # lines execute.
    event['message_id'] = event_message.id
    event_tracker.events[event_id]['message_id'] = event_message.id

    await event_message.add_reaction(hundred_emoji)
    await event_message.add_reaction(seventy_five_emoji)
    await event_message.add_reaction(fifty_emoji)
    await event_message.add_reaction(twenty_five_emoji)

    # Trigger asynchronous reminder task (only for live events)
    if not event.get('is_historical', False):
        asyncio.create_task(handle_event_reminder(bot, event_tracker, event, PACIFIC_TZ))


@bot.command(name='dungeon')
async def dungeon(ctx, *, dungeon_name: str):
    """Create a new dungeon event (1x multiplier)"""
    await create_event_with_multiplier(ctx, dungeon_name, 1.0, "🏰", discord.Color.blue())


@bot.command(name='miniboss', aliases=['mini'])
async def miniboss(ctx, *, miniboss_name: str):
    """Create a new miniboss event (1x multiplier)"""
    await create_event_with_multiplier(ctx, miniboss_name, 1.0, "⚔️", discord.Color.orange())


@bot.command(name='boss', aliases=['main', 'mainboss'])
async def boss(ctx, *, boss_name: str):
    """Create a new boss event (2x multiplier)"""
    await create_event_with_multiplier(ctx, boss_name, 2.0, "👹", discord.Color.red())


@bot.command(name='t8')
async def t8(ctx, *, t8_name: str):
    """Create a new t8 maps event (1x multiplier)"""
    await create_event_with_multiplier(ctx, t8_name, 1.0, "🗺️", discord.Color.green())


@bot.command(name='omniboss', aliases=['omni'])
async def omniboss(ctx, *, omniboss_name: str):
    """Create a new omniboss event (8x multiplier)"""
    await create_event_with_multiplier(ctx, omniboss_name, 8.0, "👑", discord.Color.purple())


@bot.command(name='add_users')
async def add_users(ctx, event_id: str, multiplier: float, *members: discord.Member):
    """Add users to an event by event_id with a multiplier

    Usage: !add_users EVENT_ID MULTIPLIER @user1 @user2 @user3
    Supports only mentions
    Multiplier affects the scoring weight for these users
    """
    try:
        # Validate multiplier
        if multiplier not in (1.0, 0.75, 0.5, 0.25):
            await ctx.send("❌ Multiplier must be exactly 1.0, 0.75, 0.5, or 0.25!")
            return

        # Check if event exists
        if event_id not in event_tracker.events:
            logger.warning(
                f"Command 'add_users' failed: Event ID '{event_id}' not found. (User: {ctx.author})"
            )
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return

        if not members:
            # This handles the case where the user provides an event_id but no users.
            await ctx.send("❌ You need to specify at least one user to add!")
            return

        event = event_tracker.events[event_id]
        member_names = [member.name for member in members]

        # Add new users with their multiplier
        for member_name in member_names:
            # Check if user already exists and remove them first
            event['manual_attendance'] = [
                user for user in event['manual_attendance'] if user['name'] != member_name
            ]
            # Add user with new multiplier
            event['manual_attendance'].append({'name': member_name, 'multiplier': multiplier})

        # Update the original event message to show the new attendance
        try:
            channel = bot.get_channel(event['channel_id'])
            if not channel:
                logger.error(
                    f"Failed to update event message: Channel {event['channel_id']} not found."
                )
                await ctx.send(f"❌ Channel with ID `{event['channel_id']}` not found.")
                return

            event_message = await channel.fetch_message(event['message_id'])

            # Create updated embed
            embed = event_message.embeds[0]

            # Update the manual attendance field using the shared helper
            embed = update_embed_manual_attendance(embed, event['manual_attendance'])

            # Update the embed
            await event_message.edit(embed=embed)

            # Re-process the message to update the event
            await event_tracker._process_message_for_events(event_message)

            # Send confirmation
            await ctx.send(
                f"✅ Successfully added {len(member_names)} user(s) to event with {multiplier}x multiplier: {', '.join(member_names)}"
            )
            logger.info(
                f"Added users to event {event_id}: {', '.join(member_names)} with {multiplier}x multiplier by {ctx.author.name}"
            )

        except Exception as e:
            # Error updating the event message
            logger.error(f"Error updating message in add_users command: {e}")
            await ctx.send(f"❌ An error occurred while adding users: {str(e)}")

    except Exception as e:
        logger.error(f"Error in add_users command: {e}")
        await ctx.send(f"❌ An error occurred while adding users: {str(e)}")


# The error handler specifically for the add_users command
@add_users.error
async def add_users_error(ctx, error):
    # Check if the error is the specific one we're looking for
    if isinstance(error, commands.MissingRequiredArgument):
        # Create a user-friendly message
        error_message = (
            "It looks like you're missing an argument! 🤔\n\n"
            "Please use the correct format: `!add_users <event_id> <multiplier> <user_names>`\n"
            "**Example:** `!add_users 1424971912928563281_1759810178 0.75 @Beetle @Mantis`\n"
            "**Fixed Multipliers:** 1.0 (full), 0.75 (partial), 0.5 (half), 0.25 (quarter)"
        )
        await ctx.send(error_message)
    else:
        # If it's a different error, you might want to log it or handle it differently
        await ctx.send("An unexpected error occurred. Please tell Waffle or Beetle.")
        logger.error(f"An unhandled error in add_users occurred: {error}")


@bot.event
async def on_reaction_add(reaction, user):
    """Handle emoji reactions for attendance"""
    if user.bot:
        return

    # Find the event by message ID
    event_id = None
    for eid, event in event_tracker.events.items():
        if event['message_id'] == reaction.message.id:
            event_id = eid
            break

    if event_id:
        emoji_str = str(reaction.emoji)
        event_tracker.add_attendance(event_id, user.id, user.name, emoji_str)
        logger.info(
            f"Added attendance: User {user.name} ({user.id}) reacted with {emoji_str} to event {event_id}"
        )


@bot.event
async def on_reaction_remove(reaction, user):
    """Handle emoji reaction removal"""
    if user.bot:
        return

    # Find the event by message ID
    event_id = None
    for eid, event in event_tracker.events.items():
        if event['message_id'] == reaction.message.id:
            event_id = eid
            break

    if event_id:
        emoji_str = str(reaction.emoji)
        event_tracker.remove_attendance(event_id, user.id, user.name, emoji_str)
        logger.info(
            f"Removed attendance: User {user.name} ({user.id}) removed {emoji_str} from event {event_id}"
        )


async def _get_events_from_args(ctx, args: str):
    """Helper to parse event query arguments for summary and data commands"""
    try:
        events_to_summarize = []
        arg_list = args.split()
        summary_title = ""

        # 1. Handle "last N"
        if len(arg_list) >= 2 and arg_list[0].lower() == "last":
            try:
                n = int(arg_list[1])
                events_to_summarize = event_tracker.get_last_n_events(n)
                summary_title = f"Last {len(events_to_summarize)} Events"
            except ValueError:
                await ctx.send("❌ Please provide a number for 'last'. Example: `last 5`.")
                return None, None

        # 2. Handle ID-to-ID or Single ID
        elif len(arg_list) > 0 and "_" in arg_list[0]:
            if len(arg_list) >= 2 and "_" in arg_list[1]:
                # Range of IDs
                events_to_summarize = event_tracker.get_events_between_ids(arg_list[0], arg_list[1])
                summary_title = f"Range: {arg_list[0]} to {arg_list[1]}"
            else:
                # Single ID
                if arg_list[0] in event_tracker.events:
                    events_to_summarize = [event_tracker.events[arg_list[0]]]
                    summary_title = f"Single Event: {events_to_summarize[0]['name']}"
                else:
                    await ctx.send(f"❌ Event ID `{arg_list[0]}` not found.")
                    return None, None

        # 3. Handle Timestamps (Legacy/Fallback)
        elif len(arg_list) > 0:
            try:
                # Attempt to parse as start [end] timestamps
                start_dt = parse_timestamp(arg_list[0])
                start_ts = start_dt.timestamp()

                if len(arg_list) >= 2:
                    end_dt = parse_timestamp(arg_list[1])
                    # If end is just a date, set to end of day
                    if len(arg_list[1]) <= 10:
                        end_dt = end_dt.replace(hour=23, minute=59, second=59)
                else:
                    end_dt = get_pacific_now()

                end_ts = end_dt.timestamp()
                events_to_summarize = event_tracker.get_events_in_range(start_ts, end_ts)
                summary_title = f"Range: {arg_list[0]}" + (
                    f" to {arg_list[1]}" if len(arg_list) >= 2 else " onwards"
                )

            except ValueError:
                await ctx.send("❌ Could not parse input. Use `help` for usage info.")
                return None, None

        else:
            # No args - default to last event
            events_to_summarize = event_tracker.get_last_n_events(1)
            summary_title = "Latest Event"

        return events_to_summarize, summary_title

    except Exception as e:
        logger.error(f"Error parsing event args: {e}")
        return None, None


@bot.command(name='summary')
async def summary(ctx, *, args: str = ""):
    """Generate attendance summary for events

    Usage:
    !summary EVENT_ID - Summary for a single event
    !summary ID1 ID2 - Summary for range of events (inclusive)
    !summary last N - Summary for the last N events
    !summary YYYY-MM-DD [YYYY-MM-DD] - Summary for date range
    """
    try:
        events_to_summarize, summary_title = await _get_events_from_args(ctx, args)

        if events_to_summarize is None:
            return

        if not events_to_summarize:
            await ctx.send("❌ No events found for the specified criteria.")
            return

        # Generate summary
        summary_data = event_tracker.generate_summary(events_to_summarize)

        # Create verification header
        first_event = events_to_summarize[0]
        last_event = events_to_summarize[-1]

        output_blocks = []
        header = "📊 Event Attendance Summary\n"
        header += f"Context: {summary_title}\n"
        header += f"Range: {first_event['name']} -> {last_event['name']}\n"
        header += f"Total Events: {len(events_to_summarize)}\n"
        output_blocks.append(header)

        # Add event details as separate blocks
        for event in summary_data['events']:
            attendees_list = []
            for user_id, (user_name, emojis) in event['attendance_by_user'].items():
                attendees_list.append(f"{user_name}")

            # Format time for this event
            dt = datetime.fromtimestamp(event['created_at'], tz=PACIFIC_TZ)
            time_str = dt.strftime('%m-%d %H:%M')
            icon = event.get('type_emoji', '')

            prefix = f"{icon} " if icon else ""
            line_header = f"{prefix}{event['name']} ({time_str})"

            if attendees_list:
                output_blocks.append(f"{line_header}: {', '.join(attendees_list)}")
            else:
                output_blocks.append(f"{line_header}: (no attendees)")

        # Add event names line for easy auditing
        event_names = [event['name'] for event in summary_data['events']]
        output_blocks.append(f"\n-------\nEvents: {', '.join(event_names)}")

        # Add weighted average summary
        weighted_summary = event_tracker.calculate_weighted_average(summary_data['events'])
        output_blocks.append(weighted_summary)

        # Send output
        await send_long_message(ctx, output_blocks)

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        logger.error(f"Error in summary command: {e}")


@bot.command(name='data')
async def data_command(ctx, *, args: str = ""):
    """Generate raw attendance data for events

    Usage:
    !data EVENT_ID - Raw data for a single event
    !data ID1 ID2 - Raw data for range of events (inclusive)
    !data last N - Raw data for the last N events
    !data YYYY-MM-DD [YYYY-MM-DD] - Raw data for date range
    """
    try:
        events_to_summarize, summary_title = await _get_events_from_args(ctx, args)

        if events_to_summarize is None:
            return

        if not events_to_summarize:
            await ctx.send("❌ No events found for the specified criteria.")
            return

        # Generate raw data (returns a list of event strings)
        raw_output_blocks = event_tracker.generate_raw_data_summary(events_to_summarize)

        # Send output
        await send_long_message(ctx, raw_output_blocks)

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        logger.error(f"Error in data command: {e}")


@bot.command(name='delete_event')
async def delete_event(ctx, event_id: str):
    """Delete an event (only the event creator can delete their own events)

    Usage: !delete_event EVENT_ID
    """
    try:
        # Check if event exists
        if event_id not in event_tracker.events:
            logger.warning(
                f"Command 'delete_event' failed: Event ID '{event_id}' not found. (User: {ctx.author})"
            )
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return

        event = event_tracker.events[event_id]

        # Check if user is the event creator or an administrator
        is_admin = ctx.author.id in ADMIN_IDS
        if event['creator_id'] != ctx.author.id and not is_admin:
            await ctx.send(
                "❌ You can only delete events that you created. This event was created by someone else."
            )
            return

        # Send confirmation message
        confirmation_embed = discord.Embed(
            title="⚠️ Confirm Event Deletion",
            description=f"Are you sure you want to delete the event **{event['name']}**?\n\nThis action cannot be undone and will remove all attendance data.",
            color=discord.Color.red(),
        )
        confirmation_embed.add_field(name="Event ID", value=event_id, inline=True)
        confirmation_embed.add_field(
            name="Created", value=f"<t:{int(event['created_at'])}:R>", inline=True
        )
        confirmation_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")

        confirmation_message = await ctx.send(embed=confirmation_embed)

        # Add reaction buttons
        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == confirmation_message.id
            )

        try:
            # Wait for user reaction (10 second timeout)
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == "✅":
                # User confirmed deletion
                try:
                    # Try to delete the Discord message
                    channel = bot.get_channel(event['channel_id'])
                    if channel:
                        try:
                            event_message = await channel.fetch_message(event['message_id'])
                            await event_message.delete()
                        except discord.NotFound:
                            # Message already deleted, that's okay
                            pass
                        except Exception as e:
                            logger.warning(
                                f"Warning: Could not delete Discord message for event {event_id}: {e}"
                            )

                    # Remove from memory
                    del event_tracker.events[event_id]

                    # Send success message
                    success_embed = discord.Embed(
                        title="✅ Event Deleted",
                        description=f"Successfully deleted event **{event['name']}**",
                        color=discord.Color.green(),
                    )
                    success_embed.add_field(name="Event ID", value=event_id, inline=True)
                    await ctx.send(embed=success_embed)

                    # Log the deletion
                    logger.info(
                        f"🗑️ Event deleted: {event['name']} (ID: {event_id}) by {ctx.author.name} ({ctx.author.id})"
                    )

                except Exception as e:
                    logger.error(f"Error deleting event {event_id}: {e}")
                    await ctx.send(f"❌ An error occurred while deleting the event: {str(e)}")

            elif str(reaction.emoji) == "❌":
                # User cancelled deletion
                await ctx.send("❌ Event deletion cancelled.")

        except asyncio.TimeoutError:
            await ctx.send("⏰ Deletion confirmation timed out. Event was not deleted.")

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        logger.error(f"Error in delete_event command: {e}")


# Error handler for delete_event command
@delete_event.error
async def delete_event_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        error_message = (
            "It looks like you're missing the event ID! 🤔\n\n"
            "Please use the correct format: `!delete_event <event_id>`\n"
            "**Example:** `!delete_event 1424971912928563281_1759810178`\n\n"
            "You can only delete events that you created."
        )
        await ctx.send(error_message)
    else:
        await ctx.send("An unexpected error occurred. Please tell Waffle or Beetle.")
        logger.error(f"An unhandled error in delete_event occurred: {error}")


@bot.command(name='missing', aliases=['whoismissing'])
async def missing(ctx, event_id1: str = None, event_id2: str = None):
    """Find users who attended one event but missed another

    Usage:
    !missing - Compare last two events (users who attended second-to-last but missed last)
    !missing EVENT_ID1 EVENT_ID2 - Compare specific events (users who attended EVENT_ID2 but missed EVENT_ID1)

    Examples:
    !missing
    !missing 1424971912928563281_1759810178 1424971912928563281_1759810179
    """
    try:
        if event_id1 is None and event_id2 is None:
            # No parameters: compare last two events
            events = list(event_tracker.events.values())
            if len(events) < 2:
                await ctx.send(
                    f"❌ Need at least 2 events to compare. Only found {len(events)} event(s)."
                )
                return

            # Sort by creation time (most recent first)
            events.sort(key=lambda x: x['created_at'], reverse=True)
            recent_event = events[0]  # Most recent
            previous_event = events[1]  # Second most recent

            event1_name = recent_event['name']
            event2_name = previous_event['name']

        elif event_id1 is not None and event_id2 is not None:
            # Two parameters: compare specific events
            if event_id1 not in event_tracker.events:
                await ctx.send(f"❌ Event with ID `{event_id1}` not found.")
                return

            if event_id2 not in event_tracker.events:
                await ctx.send(f"❌ Event with ID `{event_id2}` not found.")
                return

            recent_event = event_tracker.events[event_id1]
            previous_event = event_tracker.events[event_id2]

            event1_name = recent_event['name']
            event2_name = previous_event['name']

        else:
            await ctx.send(
                "❌ Please provide either no parameters (for last two events) or both event IDs."
            )
            return

        # Get attendees from both events
        event1_attendees = set()
        event2_attendees = set()

        # Process regular attendance (reactions)
        for user_id, (user_name, emojis) in recent_event['attendance'].items():
            event1_attendees.add(user_name)

        for user_id, (user_name, emojis) in previous_event['attendance'].items():
            event2_attendees.add(user_name)

        # Process manual attendance
        for user_data in recent_event.get('manual_attendance', []):
            if isinstance(user_data, dict):
                event1_attendees.add(user_data['name'])
            else:
                event1_attendees.add(str(user_data))

        for user_data in previous_event.get('manual_attendance', []):
            if isinstance(user_data, dict):
                event2_attendees.add(user_data['name'])
            else:
                event2_attendees.add(str(user_data))

        # Find users who attended event2 but missed event1
        missing_users = event2_attendees - event1_attendees

        # Create response
        if missing_users:
            missing_list = sorted(list(missing_users))
            embed = discord.Embed(
                title="👥 Missing Users Report",
                description=f"Users who attended **{event2_name}** but missed **{event1_name}**",
                color=discord.Color.orange(),
            )

            # Split into chunks if too many users
            if len(missing_list) > 20:
                chunks = [missing_list[i : i + 20] for i in range(0, len(missing_list), 20)]
                for i, chunk in enumerate(chunks):
                    field_name = (
                        f"Missing Users (Part {i+1})" if len(chunks) > 1 else "Missing Users"
                    )
                    embed.add_field(name=field_name, value=", ".join(chunk), inline=False)
            else:
                embed.add_field(name="Missing Users", value=", ".join(missing_list), inline=False)

            embed.add_field(
                name="Summary",
                value=f"**{len(missing_users)}** user(s) attended the previous event but missed the recent one",
                inline=False,
            )

            await ctx.send(embed=embed)

        else:
            # No missing users
            embed = discord.Embed(
                title="✅ All Previous Attendees Present",
                description=f"Everyone who attended **{event2_name}** also attended **{event1_name}**!",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Summary",
                value=f"**{len(event2_attendees)}** user(s) attended both events",
                inline=False,
            )
            await ctx.send(embed=embed)

        logger.info(
            f"Missing command used by {ctx.author.name}: {len(missing_users)} users missing from {event1_name} who attended {event2_name}"
        )

    except Exception as e:
        logger.error(f"Error in missing command: {e}")
        await ctx.send(f"❌ An error occurred while checking missing users: {str(e)}")


@missing.error
async def missing_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        error_message = (
            "It looks like you're missing an argument! 🤔\n\n"
            "**Usage:**\n"
            "• `!missing` - Compare last two events\n"
            "• `!missing EVENT_ID1 EVENT_ID2` - Compare specific events\n\n"
            "**Examples:**\n"
            "• `!missing`\n"
            "• `!missing 1424971912928563281_1759810178 1424971912928563281_1759810179`\n\n"
            "This shows users who attended the second event but missed the first event."
        )
        await ctx.send(error_message)
    else:
        await ctx.send("An unexpected error occurred. Please tell Waffle or Beetle.")
        logger.error(f"An unhandled error in missing command occurred: {error}")


@bot.command(name='backfill')
async def backfill(ctx, event_type: str, message_id: int):
    """Recover an event from a non-bot message with reactions.

    Usage: !backfill <event_type> <message_id>
    event_type: dungeon, mini, boss, t8, omni
    """
    try:
        # 1. Validate event_type
        event_type = event_type.lower()
        if event_type not in BACKFILL_TYPE_MAP:
            valid_types = ", ".join(BACKFILL_TYPE_MAP.keys())
            await ctx.send(f"❌ Invalid event type `{event_type}`. Valid types: {valid_types}")
            return

        emoji, multiplier, color = BACKFILL_TYPE_MAP[event_type]

        # 2. Fetch the original message
        try:
            target_message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.send(f"❌ Message with ID `{message_id}` not found in this channel.")
            return
        except Exception as e:
            await ctx.send(f"❌ Error fetching message: {str(e)}")
            return

        event_name = (
            target_message.content if target_message.content else f"Backfilled {event_type} Event"
        )

        # 3. Create the event entry in the tracker
        # We use the target message's creation time for the event
        created_time = target_message.created_at.astimezone(PACIFIC_TZ)
        # Use a unique ID based on the target message
        event_id = f"bf_{target_message.id}_{int(created_time.timestamp())}"

        # Check if already exists
        if event_id in event_tracker.events:
            await ctx.send(f"⚠️ Event with ID `{event_id}` already exists in the tracker.")
            return

        event = event_tracker.create_event(
            event_id=event_id,
            name=event_name,
            type_emoji=emoji,
            channel_id=ctx.channel.id,
            message_id=target_message.id,  # We'll update this to the bot's message ID soon
            creator_id=target_message.author.id,
            created_at=created_time.timestamp(),
            multiplier=multiplier,
            is_historical=True,
        )

        # 4. Import attendance from reactions as manual attendance
        imported_attendance = await event_tracker.get_attendance_from_reactions(target_message)
        event['manual_attendance'] = imported_attendance

        # 5. Send the bot's standard event message for the backfill
        embed = discord.Embed(
            title=f"{emoji} {event_name} (Backfilled)",
            description=f"This event was backfilled from message ID `{message_id}`.\nReact below if you missed it on the original message!",
            color=color,
        )
        embed.add_field(name="Original Creator", value=target_message.author.mention, inline=True)
        embed.add_field(name="Backfilled by", value=ctx.author.mention, inline=True)
        embed.add_field(name="📊Summary", value=f"`!summary {event_id}`", inline=True)
        embed.set_footer(text=f"Event ID: {event_id}")

        # Add original timestamp to embed
        embed.timestamp = created_time

        # Add manual attendance to embed for transparency
        embed = update_embed_manual_attendance(embed, imported_attendance)

        event_message = await ctx.send(embed=embed)

        # Update the event with the bot message ID
        event['message_id'] = event_message.id
        event_tracker.events[event_id]['message_id'] = event_message.id

        # Add standard reactions to the bot message
        await event_message.add_reaction(hundred_emoji)
        await event_message.add_reaction(seventy_five_emoji)
        await event_message.add_reaction(fifty_emoji)
        await event_message.add_reaction(twenty_five_emoji)

        attendee_count = len(event['attendance'])
        await ctx.send(
            f"✅ Successfully backfilled event **{event_name}** with {attendee_count} attendees!"
        )
        logger.info(f"Event backfilled: {event_name} (ID: {event_id}) by {ctx.author.name}")

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        logger.error(f"Error in backfill command: {e}")


@bot.command(name='rename', aliases=['rename_event'])
async def rename_event(ctx, event_id: str, *, new_name: str):
    """Rename an event (only the event creator can rename their own events)

    Usage: !rename EVENT_ID NEW_NAME
    Example: !rename 1424971912928563281_1759810178 "New Event Name"
    """
    try:
        # Check if event exists
        if event_id not in event_tracker.events:
            logger.warning(
                f"Command 'rename_event' failed: Event ID '{event_id}' not found. (User: {ctx.author})"
            )
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return

        event = event_tracker.events[event_id]

        # Check if user is the event creator
        if event['creator_id'] != ctx.author.id:
            await ctx.send(
                "❌ You can only rename events that you created. This event was created by someone else."
            )
            return

        # Validate new name
        if not new_name.strip():
            await ctx.send("❌ Event name cannot be empty!")
            return

        new_name = new_name.strip()
        old_name = event['name']

        # Update the event data in memory
        event['name'] = new_name

        # Update the Discord message
        try:
            channel = bot.get_channel(event['channel_id'])
            if not channel:
                await ctx.send(f"❌ Channel with ID `{event['channel_id']}` not found.")
                return

            event_message = await channel.fetch_message(event['message_id'])

            # Get the original embed
            embed = event_message.embeds[0]

            # Determine the emoji prefix based on the original title
            emoji_prefix = ""
            if embed.title.startswith("🏰 "):
                emoji_prefix = "🏰 "
            elif embed.title.startswith("⚔️ "):
                emoji_prefix = "⚔️ "
            elif embed.title.startswith("🗺️ "):
                emoji_prefix = "🗺️ "
            elif embed.title.startswith("👹 "):
                emoji_prefix = "👹 "
            elif embed.title.startswith("👑 "):
                emoji_prefix = "👑 "

            # Update the embed title with the new name
            embed.title = f"{emoji_prefix}{new_name}"

            # Update the embed
            await event_message.edit(embed=embed)

            # Send success message
            success_embed = discord.Embed(
                title="✅ Event Renamed",
                description=f"Successfully renamed event from **{old_name}** to **{new_name}**",
                color=discord.Color.green(),
            )
            success_embed.add_field(name="Event ID", value=event_id, inline=True)
            success_embed.add_field(name="Old Name", value=old_name, inline=True)
            success_embed.add_field(name="New Name", value=new_name, inline=True)

            await ctx.send(embed=success_embed)

            # Log the rename
            logger.info(
                f"🔄 Event renamed: {old_name} → {new_name} (ID: {event_id}) by {ctx.author.name} ({ctx.author.id})"
            )

        except discord.NotFound:
            await ctx.send(
                "❌ The original event message was not found. The event data has been updated in memory, but the Discord message could not be updated."
            )
            logger.warning(f"⚠️ Event message not found for rename: {event_id}")
        except Exception as e:
            logger.error(f"Error updating Discord message for rename: {e}")
            await ctx.send(f"❌ An error occurred while updating the Discord message: {str(e)}")

    except Exception as e:
        logger.error(f"Error in rename_event command: {e}")
        await ctx.send(f"❌ An error occurred while renaming the event: {str(e)}")


@rename_event.error
async def rename_event_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        error_message = (
            "It looks like you're missing an argument! 🤔\n\n"
            "Please use the correct format: `!rename <event_id> <new_name>`\n"
            "**Example:** `!rename 1424971912928563281_1759810178 \"New Event Name\"`\n\n"
            "You can only rename events that you created."
        )
        await ctx.send(error_message)
    else:
        await ctx.send("An unexpected error occurred. Please tell Waffle or Beetle.")
        logger.error(f"An unhandled error in rename_event occurred: {error}")


@bot.command(name='reminders')
async def reminders(ctx, action: str = None):
    """Toggle reminder DMs on or off for yourself.

    Usage: !reminders on | off
    """
    if action is None:
        # Check current status
        is_opted_out = ctx.author.id in event_tracker.opted_out_users
        status = "OFF" if is_opted_out else "ON"
        await ctx.send(f"🔔 Your reminders for this bot are currently: **{status}**")
        return

    action = action.lower()
    if action == "on":
        if event_tracker.toggle_reminders(ctx.author.id, True):
            await ctx.send(
                "✅ Reminders turned **ON**. You will receive DMs for events you missed."
            )
        else:
            await ctx.send("ℹ️ Reminders were already **ON**.")
    elif action == "off":
        if event_tracker.toggle_reminders(ctx.author.id, False):
            await ctx.send(
                "✅ Reminders turned **OFF**. You will no longer receive DM notifications."
            )
        else:
            await ctx.send("ℹ️ Reminders were already **OFF**.")
    else:
        await ctx.send("❌ Invalid action. Use `!reminders on` or `!reminders off`.")


@bot.command(name='help_events')
async def help_events(ctx):
    """Show help for event commands"""
    embed = discord.Embed(
        title="🤖 Event Tracker Bot Commands",
        description="Commands for managing events and attendance tracking with weighted scoring",
        color=discord.Color.purple(),
    )

    embed.add_field(
        name="📅 Create Events",
        value=f"`{BOT_PREFIX}dungeon Dungeon Name` - 🏰 Dungeon (1x multiplier)\n`{BOT_PREFIX}miniboss Miniboss Name` - ⚔️ Miniboss (1x multiplier)\n`{BOT_PREFIX}mini Miniboss Name` - ⚔️ Miniboss (1x multiplier, alias)\n`{BOT_PREFIX}t8 T8 Name` - 🗺️ T8 Maps (1x multiplier)\n`{BOT_PREFIX}boss Boss Name` - 👹 Boss (2x multiplier)\n`{BOT_PREFIX}main Boss Name` - 👹 Boss (2x multiplier, alias)\n`{BOT_PREFIX}mainboss Boss Name` - 👹 Boss (2x multiplier, alias)\n`{BOT_PREFIX}omniboss Omniboss Name` - 👑 Omniboss (8x multiplier)\n`{BOT_PREFIX}omni Omniboss Name` - 👑 Omniboss (8x multiplier, alias)\n\nCreates events with different multipliers that affect final scoring. Omniboss events give 8x points!",
        inline=False,
    )

    embed.add_field(
        name="📊 Generate Summary",
        value=f"`{BOT_PREFIX}summary ID1 ID2` - Summary for range of events (inclusive)\n`{BOT_PREFIX}summary EVENT_ID` - Detailed summary for single event\n`{BOT_PREFIX}summary last N` - Summary for the last N events\n`{BOT_PREFIX}summary YYYY-MM-DD` - Summary for a specific date\n\n**Examples:**\n• `{BOT_PREFIX}summary last 5` (Summary of last 5 runs)\n• `{BOT_PREFIX}summary 123_456 123_789` (ID range summary)\n• `{BOT_PREFIX}summary 2024-01-01` (Everything from Jan 1 onwards)\n\nThis command identifies exactly which events are included in the output header for verification.",
        inline=False,
    )

    embed.add_field(
        name="🔢 Raw Data",
        value=f"`{BOT_PREFIX}data last N` - Raw attendance data with participation weights\n`{BOT_PREFIX}data ID1 ID2` - Raw data for range of events\n\n**Example:**\n• `{BOT_PREFIX}data last 3` (Raw data for the last 3 events)\n\nFormat: `[event_id] [type] Name: User (score), ...`",
        inline=False,
    )

    embed.add_field(
        name="👥 Add Users to Event",
        value=f"`{BOT_PREFIX}add_users EVENT_ID MULTIPLIER @user1 @user2 @user3`\nManually add users to an existing event with fixed multiplier scoring\n\n**Examples:**\n• `{BOT_PREFIX}add_users 1234567890_1234567890 1.0 @alice @bob` (full attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.75 @charlie` (partial attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.5 @david` (half attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.25 @eve` (quarter attendance)\n\n**Fixed Multipliers:** 1.0 (full), 0.75 (partial), 0.5 (half), 0.25 (quarter). Updates the original event message automatically.",
        inline=False,
    )

    embed.add_field(
        name="🗑️ Delete Event",
        value=f"`{BOT_PREFIX}delete_event EVENT_ID`\nDelete an event (only the event creator can delete their own events)\n\n**Example:**\n• `{BOT_PREFIX}delete_event 1234567890_1234567890`\n\n⚠️ **Warning:** This action cannot be undone and will remove all attendance data!",
        inline=False,
    )

    embed.add_field(
        name="👥 Find Missing Users",
        value=f"`{BOT_PREFIX}missing [EVENT_ID1 EVENT_ID2]`\nFind users who attended one event but missed another\n\n**Examples:**\n• `{BOT_PREFIX}missing` - Compare last two events\n• `{BOT_PREFIX}missing 1234567890_1234567890 1234567890_1234567891` - Compare specific events\n\nShows users who attended the second event but missed the first event.",
        inline=False,
    )

    embed.add_field(
        name="🔄 Rename Event",
        value=f"`{BOT_PREFIX}rename EVENT_ID NEW_NAME`\nRename an event (only the event creator can rename their own events)\n\n**Examples:**\n• `{BOT_PREFIX}rename 1234567890_1234567890 \"Updated Event Name\"`\n• `{BOT_PREFIX}rename_event 1234567890_1234567890 \"New Name\"`\n\nUpdates both the Discord message and the event data in memory.",
        inline=False,
    )

    embed.add_field(
        name="🔙 Backfill Event",
        value=f"`{BOT_PREFIX}backfill <type> <message_id>`\nRecover an event from a non-bot message with reactions. The message text becomes the event name.\n\n**Types:** dungeon, mini, boss, t8, omni\n**Example:** `{BOT_PREFIX}backfill boss 123456789012345678`",
        inline=False,
    )

    embed.add_field(
        name="🔔 Reminder Preferences",
        value=f"`{BOT_PREFIX}reminders [on|off]`\nToggle DM reminders for events you missed but attended previously.\n\n**Examples:**\n• `{BOT_PREFIX}reminders off` - Opt out of DMs\n• `{BOT_PREFIX}reminders on` - Opt back in to DMs",
        inline=False,
    )

    embed.add_field(
        name="🎯 Attendance & Scoring",
        value="**Emoji Reactions (Custom Emojis):**\n• `share_100` - 100% attendance (1.0x)\n• `share_75` - 75% attendance (0.75x)\n• `share_50` - 50% attendance (0.5x)\n• `share_25` - 25% attendance (0.25x)\n\n**Manual Attendance:**\n• Added via `add_users` command with fixed multipliers\n• Only supports: 1.0, 0.75, 0.5, 0.25\n• Example: `!add_users EVENT_ID 0.75 @user` gives 0.75x participation\n\n**Final Score = Event Multiplier × Participation Multiplier**\n• Dungeon/Miniboss/T8: 1x multiplier\n• Boss events: 2x multiplier\n• Omniboss events: 8x multiplier",
        inline=False,
    )

    embed.add_field(
        name="❓ Help", value=f"`{BOT_PREFIX}help_events`\nShows this help message", inline=False
    )

    embed.add_field(
        name="📧 Get Event Summary in DM",
        value="Every event message now includes a **📊 Get Summary in DM** button. Click it to receive a detailed summary of that specific event in your DMs, including:\n• Complete attendee list with emoji reactions\n• Individual weighted scores for each participant\n• Event details (creator, multiplier, creation time)\n• Manual attendance entries\n\nPerfect for getting detailed info without cluttering the channel!",
        inline=False,
    )

    embed.add_field(
        name="ℹ️ How to Attend",
        value="React to event messages with the custom emoji reactions to register your attendance level. The bot automatically tracks and calculates weighted scores across all events!",
        inline=False,
    )

    await ctx.send(embed=embed)


def run() -> None:
    """Run the bot process with retry-on-disconnect behavior."""
    if not DISCORD_TOKEN:
        logger.error("Error: DISCORD_TOKEN not found in environment variables")
        logger.error("Please create a .env file with your Discord bot token")
        raise SystemExit(1)

    retry_delay = 30  # seconds to wait between connection attempts

    while True:
        try:
            logger.info("Attempting to connect to Discord...")
            # Passing log_handler=None prevents discord.py from setting up its own logging
            # and duplicating our custom logging configuration.
            bot.run(DISCORD_TOKEN, log_handler=None)

            # If bot.run() returns normally, it was likely a clean shutdown
            logger.info("Bot execution finished normally.")
            break

        except Exception as e:
            logger.error(f"Bot failed to start or connection lost: {e}")
            logger.info(f"Retrying in {retry_delay} seconds... (Press Ctrl+C to stop)")
            time.sleep(retry_delay)


if __name__ == "__main__":
    run()

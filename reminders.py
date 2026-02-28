"""
# Event Reminder Logic

This feature helps maintain event momentum by reminding active participants from a previous event
to react to a new one if they haven't done so within 2 minutes.

## Core Rules
1. **The 2-Hour Session Window**: A reminder is only triggered if the most recent previous event
   was created within the last 2 hours (7200 seconds). If the gap is larger, the bot assumes
   it's a new session and won't send DMs.
2. **The 120-Second Wait**: The bot waits exactly 120 seconds after a new event is created
   before checking participation. This allows active users time to react naturally.
3. **The "Recently Active" Set**: The bot only considers users who reacted to the previous event.
   Manually added users and the creator of the new event are ignored to prevent spam.
4. **The "Missing" Delta**: A DM is only sent to users who reacted to the previous event
   but have not yet reacted to the new one.
5. **Polite Delivery**: DMs are throttled (1.0s delay) and include a direct jump link
   to the event message for easy participation.

## Technical Details
- **Trigger**: Called via asyncio.create_task() in create_event_with_multiplier.
- **Filtering**: Specifically excludes bots and the event creator.
- **Resilience**: Fetches users via fetch_user if they aren't in the local cache.
"""

import asyncio
import discord
import logging
from datetime import datetime

logger = logging.getLogger('bot.reminders')


async def handle_event_reminder(bot, event_tracker, new_event, PACIFIC_TZ):
    """
    Background task to send reminders to users who attended the previous event
    but haven't reacted to the new one yet.
    """
    try:
        # 0. Safety Check: If event is already historical or too old, skip
        if new_event.get('is_historical', False):
            return

        current_time = datetime.now(PACIFIC_TZ).timestamp()
        if (current_time - new_event['created_at']) > 600:
            logger.info(f"Reminder skipped for '{new_event['name']}': Event is too old (>10m).")
            return

        # 1. Find previous event
        prev_event = event_tracker.get_most_recent_before(new_event['id'])
        if not prev_event:
            logger.info(f"Reminder skipped for '{new_event['name']}': No previous event found.")
            return

        # 2. Check 2-hour threshold (7200 seconds)
        time_diff = new_event['created_at'] - prev_event['created_at']
        if time_diff > 7200:
            logger.info(
                f"Reminder skipped for '{new_event['name']}': Previous event was {time_diff/3600:.1f} hours ago."
            )
            return

        logger.info(
            f"Reminder scheduled for '{new_event['name']}' in 120s. Previous event: '{prev_event['name']}'"
        )

        # 3. Wait 120 seconds
        await asyncio.sleep(120)

        # 4. Fetch the message again to get LATEST reactions
        channel = bot.get_channel(new_event['channel_id'])
        if not channel:
            logger.error(f"Could not find channel {new_event['channel_id']} for reminders")
            return

        try:
            message = await channel.fetch_message(new_event['message_id'])
            jump_url = message.jump_url
        except Exception as e:
            logger.error(f"Could not fetch message {new_event['message_id']} for reminders: {e}")
            return

        # 5. Identify current attendees from ACTUAL reactions on the NEW message
        new_attendees = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    new_attendees.add(user.id)

        # 6. Re-fetch reactions for the PREVIOUS message to ensure we have late joiners
        prev_attendees = set()
        prev_channel = bot.get_channel(prev_event['channel_id'])
        if prev_channel:
            try:
                prev_message = await prev_channel.fetch_message(prev_event['message_id'])
                for reaction in prev_message.reactions:
                    async for user in reaction.users():
                        if not user.bot:
                            prev_attendees.add(user.id)
            except Exception as e:
                logger.warning(
                    f"Could not re-fetch previous message {prev_event['message_id']}: {e}. Falling back to memory."
                )
                # Fallback to in-memory attendance if message is gone/error
                prev_attendees = set(prev_event['attendance'].keys())
        else:
            prev_attendees = set(prev_event['attendance'].keys())

        # 7. Identify those who haven't reacted yet
        # Identify the delta
        missing_ids = prev_attendees - new_attendees

        if not missing_ids:
            logger.info(f"No reminders needed for '{new_event['name']}'. Everyone already reacted.")
            return

        logger.info(f"Sending reminders for '{new_event['name']}' to {len(missing_ids)} users.")

        icon = new_event.get('type_emoji', '')
        event_name = new_event['name']

        # Use a mention for the creator to provide a rich link
        creator_id = new_event['creator_id']
        creator_mention = f"<@{creator_id}>"

        # 8. Send DMs with throttling
        for user_id in missing_ids:
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except Exception:
                    continue

            if user.bot:
                continue

            try:
                embed = discord.Embed(
                    title=f"🛡️ {icon} {event_name}",
                    description=f"{creator_mention} started a new event and you haven't reacted yet!",
                    color=discord.Color.blue(),
                )
                embed.add_field(
                    name="Action", value=f"[**Jump to Event & React**]({jump_url})", inline=False
                )

                await user.send(embed=embed)
                logger.info(f"Sent reminder DM to {user.name}")

                # Throttle to avoid rate limits
                await asyncio.sleep(1.0)
            except discord.Forbidden:
                logger.warning(f"Could not DM {user.name} (DMs closed)")
            except Exception as e:
                logger.error(f"Failed to DM {user.name}: {e}")

    except Exception as e:
        logger.error(f"Error in handle_event_reminder: {e}")

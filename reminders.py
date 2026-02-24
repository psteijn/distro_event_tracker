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
        # 1. Find previous event
        prev_event = event_tracker.get_most_recent_before(new_event['id'])
        if not prev_event:
            logger.info(f"Reminder skipped for '{new_event['name']}': No previous event found.")
            return

        # 2. Check 2-hour threshold (7200 seconds)
        time_diff = new_event['created_at'] - prev_event['created_at']
        if time_diff > 7200:
            logger.info(f"Reminder skipped for '{new_event['name']}': Previous event was {time_diff/3600:.1f} hours ago.")
            return

        logger.info(f"Reminder scheduled for '{new_event['name']}' in 120s. Previous event: '{prev_event['name']}'")
        
        # 3. Wait 120 seconds
        await asyncio.sleep(120)

        # 4. Identify those who haven't reacted yet
        # Get users from previous event (only reactions)
        prev_attendees = set(prev_event['attendance'].keys())
        
        # Get users from new event (reactions)
        new_attendees = set(new_event['attendance'].keys())
        
        # Identify the delta
        missing_ids = prev_attendees - new_attendees
        
        # Exclude creator
        creator_id = new_event['creator_id']
        missing_ids.discard(creator_id)

        if not missing_ids:
            logger.info(f"No reminders needed for '{new_event['name']}'. Everyone already reacted.")
            return

        logger.info(f"Sending reminders for '{new_event['name']}' to {len(missing_ids)} users.")

        # 5. Fetch Discord objects for messaging
        channel = bot.get_channel(new_event['channel_id'])
        if not channel:
            logger.error(f"Could not find channel {new_event['channel_id']} for jump link")
            return
            
        try:
            message = await channel.fetch_message(new_event['message_id'])
            jump_url = message.jump_url
        except Exception as e:
            logger.error(f"Could not fetch message {new_event['message_id']}: {e}")
            return

        icon = new_event.get('type_emoji', '')
        event_name = new_event['name']
        
        # Fetch creator for the DM context
        creator = bot.get_user(creator_id)
        creator_name = creator.name if creator else "a teammate"

        # 6. Send DMs with throttling
        for user_id in missing_ids:
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except:
                    continue
            
            if user.bot:
                continue

            try:
                embed = discord.Embed(
                    title="🛡️ Event Reminder",
                    description=f"A new **{icon} {event_name}** event was started by **{creator_name}**!

You're receiving this because you reacted to an event in the last 2 hours.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Action Required",
                    value=f"[**Click here to jump to the event and react!**]({jump_url})",
                    inline=False
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

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional
import pytz
from config import DISCORD_TOKEN, BOT_PREFIX, EVENT_CHANNEL_ID, DEFAULT_EMOJI

# Pacific timezone (handles daylight savings automatically)
PACIFIC_TZ = pytz.timezone('US/Pacific')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

# In-memory storage for events (will be replaced with database later)
events_storage = {}

class EventTracker:
    def __init__(self):
        self.events = {}
    
    def create_event(self, event_id: str, name: str, channel_id: int, message_id: int, creator_id: int, multiplier: float = 1.0) -> Dict:
        """Create a new event with a multiplier for scoring"""
        event = {
            'id': event_id,
            'name': name,
            'channel_id': channel_id,
            'message_id': message_id,
            'creator_id': creator_id,
            'created_at': get_pacific_now().timestamp(),
            'multiplier': multiplier,
            'attendance': {}
        }
        self.events[event_id] = event
        return event
    
    def add_attendance(self, event_id: str, user_id: int, user_name: str, emoji: str) -> bool:
        """Add attendance record for a user"""
        if event_id in self.events:
            if user_id not in self.events[event_id]['attendance']:
                self.events[event_id]['attendance'][user_id] = (user_name, [])
            if emoji not in self.events[event_id]['attendance'][user_id][1]:
                self.events[event_id]['attendance'][user_id][1].append(emoji)
            return True
        return False
    
    def remove_attendance(self, event_id: str, user_id: int, user_name: str, emoji: str) -> bool:
        """Remove attendance record for a user"""
        if event_id in self.events and user_id in self.events[event_id]['attendance']:
            if emoji in self.events[event_id]['attendance'][user_id][1]:
                self.events[event_id]['attendance'][user_id][1].remove(emoji)
                if not self.events[event_id]['attendance'][user_id][1]:
                    del self.events[event_id]['attendance'][user_id]
            return True
        return False
    
    def get_events_in_range(self, start_timestamp_sec: int, end_timestamp_sec: int) -> List[Dict]:
        """Get all events within a date range"""
        filtered_events = []
        for event in self.events.values():
            event_timestamp_sec = event['created_at']
            
            if start_timestamp_sec <= event_timestamp_sec <= end_timestamp_sec:
                filtered_events.append(event)
        return filtered_events
    
    def generate_summary(self, events: List[Dict]) -> Dict:
        """Generate attendance summary for events"""
        summary = {
            'generated_at': get_pacific_now().isoformat(),
            'total_events': len(events),
            'events': []
        }
        
        for event in events:
            event_summary = {
                'id': event['id'],
                'name': event['name'],
                'multiplier': event['multiplier'],
                'created_at': event['created_at'],
                'total_attendees': len(event['attendance']),
                'attendance_by_user': event['attendance']
            }
            summary['events'].append(event_summary)
        
        return summary
    
    def calculate_weighted_average(self, events: List[Dict]) -> str:
        """Calculate weighted average of attendees across all events"""
        if not events:
            return "No events to analyze"
        
        # Count attendance for each user across all events with multipliers
        user_attendance_score = {}
        total_events = len(events)
        
        for event in events:
            multiplier = event.get('multiplier', 1.0)  # Default to 1.0 if no multiplier
            for user_id, (user_name, emojis) in event['attendance_by_user'].items():
                if user_name not in user_attendance_score:
                    user_attendance_score[user_name] = 0
                user_attendance_score[user_name] += multiplier
        
        if not user_attendance_score:
            return "No attendees found"
        
        # Sort users by attendance score (descending)
        sorted_users = sorted(user_attendance_score.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate weighted average with multipliers
        weighted_summary = []
        for user_name, score in sorted_users:
            weighted_summary.append(f"{user_name} ({score:.1f})")
        
        return f"ALL EVENTS: {', '.join(weighted_summary)}"  # Show all attendees with scores
    
    async def reconstruct_from_history(self, bot):
        """Reconstruct events from message history"""
        print("🔄 Reconstructing events from message history...")
        reconstructed_count = 0
        
        channel = bot.get_channel(int(EVENT_CHANNEL_ID))
        if channel:
            print(f"📖 Scanning channel: {channel.name}")
            async for message in channel.history(limit=1000):
                if await self._process_message_for_events(message):
                    reconstructed_count += 1
        else:
            print(f"❌ Channel {EVENT_CHANNEL_ID} not found")

        print(f"✅ Reconstructed {reconstructed_count} events from message history")
        return reconstructed_count
    
    async def _process_message_for_events(self, message):
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
        
        if embed.title.startswith("🏰 "):
            # Dungeon event
            event_name = embed.title.replace("🏰 ", "")
            multiplier = 1.0
        elif embed.title.startswith("⚔️ "):
            # Miniboss event
            event_name = embed.title.replace("⚔️ ", "")
            multiplier = 1.0
        elif embed.title.startswith("👹 "):
            # Boss event
            event_name = embed.title.replace("👹 ", "")
            multiplier = 2.0
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
        
        for field in embed.fields:
            if field.name == "Created by":
                # Extract user ID from mention
                creator_mention = field.value
                if creator_mention.startswith("<@") and creator_mention.endswith(">"):
                    creator_id = int(creator_mention[2:-1])
            elif field.name == "Multiplier":
                # Extract multiplier from embed field
                multiplier_text = field.value
                if multiplier_text.endswith("x"):
                    try:
                        embed_multiplier = float(multiplier_text[:-1])
                    except ValueError:
                        embed_multiplier = multiplier  # Fallback to detected multiplier
        
        # If we can't find creator info, skip this event
        if not creator_id:
            return False
        
        # Extract timestamp from event_id (format: message_id_timestamp)
        created_at_timestamp = message.created_at.timestamp()
        
        # Create event entry
        event = {
            'id': event_id,
            'name': event_name,
            'channel_id': message.channel.id,
            'message_id': message.id,
            'creator_id': creator_id,
            'created_at': created_at_timestamp,
            'multiplier': embed_multiplier,
            'attendance': {}
        }
        
        # Process reactions to get attendance
        await self._process_reactions_for_event(event, message)

        # Process manual attendance
        for field in message.embeds[0].fields:
            if field.name == "Manual Attendance":
                for user in field.value.split(', '):
                    print(f"TODO: process manual attendance for {user}")
        
        # Store the event
        self.events[event_id] = event
        print(f"📝 Reconstructed event: {event_name} (ID: {event_id}, multiplier: {embed_multiplier}x, attendance: {[user[0] for user in event['attendance'].values()]})")
        return True
    
    async def _process_reactions_for_event(self, event, message):
        """Process reactions on a message to reconstruct attendance"""
        try:
            # Get all reactions on the message
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji)
                
                # Get users who reacted
                async for user in reaction.users():
                    if user.bot:
                        continue  # Skip bot reactions
                    
                    # Add attendance record
                    if user.id not in event['attendance']:
                        event['attendance'][user.id] = (user.name, [])
                    
                    if emoji_str not in event['attendance'][user.id][1]:
                        event['attendance'][user.id][1].append(emoji_str)
                        
        except Exception as e:
            print(f"⚠️ Error processing reactions for event {event['name']}: {e}")

# Initialize event tracker
event_tracker = EventTracker()

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
    
    raise ValueError(f"Unable to parse timestamp: {timestamp_str}. Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, epoch seconds")

def get_pacific_now() -> datetime:
    """Get current time in Pacific timezone"""
    return datetime.now(PACIFIC_TZ)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Reconstruct events from message history
    try:
        reconstructed_count = await event_tracker.reconstruct_from_history(bot)
        print(f'🚀 Bot ready! Reconstructed {reconstructed_count} events from history.')
    except Exception as e:
        print(f'❌ Error during event reconstruction: {e}')
        print('🚀 Bot ready! (Running without historical events)')

async def create_event_with_multiplier(ctx, event_name: str, multiplier: float, emoji: str, color: discord.Color):
    """Helper function to create events with multipliers"""
    if EVENT_CHANNEL_ID and str(ctx.channel.id) != EVENT_CHANNEL_ID:
        await ctx.send(f"Events can only be created in the designated event channel.")
        return
    
    # Generate unique event ID
    event_id = f"{ctx.message.id}_{int(get_pacific_now().timestamp())}"
    
    # Create event with multiplier
    event = event_tracker.create_event(
        event_id=event_id,
        name=event_name,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id,
        creator_id=ctx.author.id,
        multiplier=multiplier
    )
    
    # Send event message
    embed = discord.Embed(
        title=f"{emoji} {event_name}",
        description=f"React with {DEFAULT_EMOJI} to register your attendance!",
        color=color
    )
    embed.add_field(name="Created by", value=ctx.author.mention, inline=True)
    embed.add_field(name="Multiplier", value=f"{multiplier}x", inline=False)
    embed.set_footer(text=f"Event ID: {event_id}")
    
    event_message = await ctx.send(embed=embed)
    
    # Add default emoji reaction
    await event_message.add_reaction(DEFAULT_EMOJI)
    
    # Update event with the actual message ID
    event['message_id'] = event_message.id
    event_tracker.events[event_id]['message_id'] = event_message.id

@bot.command(name='dungeon')
async def dungeon(ctx, *, dungeon_name: str):
    """Create a new dungeon event (1x multiplier)"""
    await create_event_with_multiplier(ctx, dungeon_name, 1.0, "🏰", discord.Color.blue())

@bot.command(name='miniboss')
async def miniboss(ctx, *, miniboss_name: str):
    """Create a new miniboss event (1x multiplier)"""
    await create_event_with_multiplier(ctx, miniboss_name, 1.0, "⚔️", discord.Color.orange())

@bot.command(name='boss')
async def boss(ctx, *, boss_name: str):
    """Create a new boss event (2x multiplier)"""
    await create_event_with_multiplier(ctx, boss_name, 2.0, "👹", discord.Color.red())

@bot.command(name='add_users')
async def add_users(ctx, event_id: str, *members: discord.Member):
    """Add users to an event by event_id
    
    Usage: !add_users EVENT_ID user1 user2 @user3 DisplayName
    Supports both usernames and mentions
    """
    try:
        # Check if event exists
        if event_id not in event_tracker.events:
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return
        
        if not members:
            # This handles the case where the user provides an event_id but no users.
            await ctx.send("❌ You need to specify at least one user to add!")
            return
        
        event = event_tracker.events[event_id]
        member_names = [member.display_name for member in members]
        
        # Update the original event message to show the new attendance
        try:
            channel = bot.get_channel(event['channel_id'])
            if not channel:
                await ctx.send(f"❌ Channel with ID `{event['channel_id']}` not found.")
                return

            event_message = await channel.fetch_message(event['message_id'])
            
            # Create updated embed
            embed = event_message.embeds[0]

            found_existing_field = False
            for field in embed.fields:
                if field.name == "Manual Attendance":
                    field.value = f"{field.value}, {', '.join(member_names)}"
                    found_existing_field = True
                    break
            if not found_existing_field:
                embed.add_field(name="Manual Attendance", value=f"{', '.join(member_names)}", inline=True)

            # Update the embed
            await event_message.edit(embed=embed)

            # Send confirmation
            await ctx.send(f"✅ Successfully added {len(member_names)} user(s) to event: {', '.join(member_names)}")
            print(f"Added users to event {event_id}: {', '.join(member_names)} by {ctx.author.name}")
                
        except Exception as e:
            # Error updating the event message
            await ctx.send(f"❌ An error occurred while adding users: {str(e)}")
            print(f"Error in add_users command: {e}")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred while adding users: {str(e)}")
        print(f"Error in add_users command: {e}")

# The error handler specifically for the add_users command
@add_users.error
async def add_users_error(ctx, error):
    # Check if the error is the specific one we're looking for
    if isinstance(error, commands.MissingRequiredArgument):
        # Create a user-friendly message
        error_message = (
            "It looks like you're missing an argument! 🤔\n\n"
            "Please use the correct format: `!add_users <event_id> <user_names>`\n"
            "**Example:** `!add_users 1424971912928563281_1759810178 @Beetle @Mantis`"
        )
        await ctx.send(error_message)
    else:
        # If it's a different error, you might want to log it or handle it differently
        await ctx.send("An unexpected error occurred. Please tell Waffle or Beetle.")
        print(f"An unhandled error in add_users occurred: {error}")

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
        print(f"Added attendance: User {user.name} (display name: {user.display_name}) ({user.id}) reacted with {emoji_str} to event {event_id}")  # user.name is the account name

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
        print(f"Removed attendance: User {user.name} ({user.id}) removed {emoji_str} from event {event_id}")  # user.name is the account name

@bot.command(name='summary')
async def generate_summary(ctx, start_timestamp: str, end_timestamp: str = None):
    """Generate attendance summary for events in a date range
    
    Supports multiple timestamp formats:
    - YYYY-MM-DD (date only)
    - YYYY-MM-DD HH:MM:SS (full timestamp)
    - YYYY-MM-DD HH:MM (date with time)
    - YYYY/MM/DD (alternative date format)
    - MM/DD/YYYY (US date format)
    - Epoch timestamp (seconds since 1970-01-01)
    
    If only one timestamp is provided, fetches all events after that timestamp.
    """
    try:
        # Parse start timestamp
        start_timestamp_sec = parse_timestamp(start_timestamp).timestamp()
        
        # Parse end timestamp or set to current time if not provided
        if end_timestamp is None:
            end_dt = get_pacific_now()
        else:
            end_dt = parse_timestamp(end_timestamp)
            # If only date was provided, extend end time to end of day
            if len(end_timestamp.split()) == 1 and not end_timestamp.isdigit():
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
        end_timestamp_sec = end_dt.timestamp()
        
        # Get events in range
        events_in_range = event_tracker.get_events_in_range(start_timestamp_sec, end_timestamp_sec)
        
        if not events_in_range:
            if end_timestamp is None:
                await ctx.send(f"No events found after {start_timestamp}")
            else:
                await ctx.send(f"No events found in the date range {start_timestamp} to {end_timestamp}")
            return
        
        # Generate summary
        summary = event_tracker.generate_summary(events_in_range)
        
        # Create simple text format
        text_output = f"📊 Event Attendance Summary\n"
        if end_timestamp is None:
            text_output += f"Events after {start_timestamp}\n"
        else:
            text_output += f"Events from {start_timestamp} to {end_timestamp}\n"
        text_output += f"Total Events: {summary['total_events']}\n\n"
        
        # Add event details in simple format
        for event in summary['events']:
            attendees_list = []
            for user_id, (user_name, emojis) in event['attendance_by_user'].items():
                attendees_list.append(f"{user_name}")
            
            if attendees_list:
                text_output += f"{event['name']}: {', '.join(attendees_list)}\n"
            else:
                text_output += f"{event['name']}: (no attendees)\n"
        
        # Add weighted average summary
        weighted_summary = event_tracker.calculate_weighted_average(summary['events'])
        text_output += f"\n{weighted_summary}\n"
        
        # Send the text output
        if len(text_output) > 2000:
            # Split into multiple messages if too long
            chunks = [text_output[i:i+1900] for i in range(0, len(text_output), 1900)]
            for chunk in chunks:
                await ctx.send(f"```\n{chunk}\n```")
        else:
            await ctx.send(f"```\n{text_output}\n```")
            
    except ValueError as e:
        await ctx.send(f"Invalid timestamp format. Error: {str(e)}")
    except Exception as e:
        await ctx.send(f"An error occurred while generating the summary: {str(e)}")

@bot.command(name='help_events')
async def help_events(ctx):
    """Show help for event commands"""
    embed = discord.Embed(
        title="🤖 Event Tracker Bot Commands",
        description="Commands for managing events and attendance",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="Create Events",
        value=f"`{BOT_PREFIX}dungeon Dungeon Name` - 🏰 Dungeon (1x multiplier)\n`{BOT_PREFIX}miniboss Miniboss Name` - ⚔️ Miniboss (1x multiplier)\n`{BOT_PREFIX}boss Boss Name` - 👹 Boss (2x multiplier)\n\nCreates events with different multipliers that affect scoring",
        inline=False
    )
    
    embed.add_field(
        name="Generate Summary",
        value=f"`{BOT_PREFIX}summary START_TIMESTAMP [END_TIMESTAMP]`\nGenerates attendance summary for events in time range\n\n**Supported timestamp formats:**\n• `YYYY-MM-DD` (date only)\n• `YYYY-MM-DD HH:MM:SS` (full timestamp)\n• `YYYY-MM-DD HH:MM` (date with time)\n• `YYYY/MM/DD` (alternative format)\n• `MM/DD/YYYY` (US format)\n• `1234567890` (epoch seconds)\n\n**Examples:**\n• `{BOT_PREFIX}summary 2024-01-01` (all events after Jan 1)\n• `{BOT_PREFIX}summary 2024-01-01 2024-01-31` (events in January)\n• `{BOT_PREFIX}summary 2024-01-01 09:00:00 2024-01-01 18:00:00` (events on Jan 1, 9am-6pm)\n• `{BOT_PREFIX}summary 1704067200` (all events after epoch timestamp)",
        inline=False
    )
    
    embed.add_field(
        name="Add Users to Event",
        value=f"`{BOT_PREFIX}add_users EVENT_ID @user1 @user2 @user3`\nManually add users to an existing event\n\n**Examples:**\n• `{BOT_PREFIX}add_users 1234567890_1234567890 @alice @bob`\n\nOnly supports mentions. Updates the original event message.",
        inline=False
    )

    embed.add_field(
        name="Help",
        value=f"`{BOT_PREFIX}help_events`\nShows this help message",
        inline=False
    )
    
    embed.add_field(
        name="How to Attend",
        value="React to event messages with emojis to register attendance",
        inline=False
    )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables")
        print("Please create a .env file with your Discord bot token")
        exit(1)
    
    bot.run(DISCORD_TOKEN)

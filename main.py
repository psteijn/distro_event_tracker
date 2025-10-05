import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional
from config import DISCORD_TOKEN, BOT_PREFIX, EVENT_CHANNEL_ID, DEFAULT_EMOJI

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
    
    def create_event(self, event_id: str, name: str, channel_id: int, message_id: int, creator_id: int) -> Dict:
        """Create a new event"""
        event = {
            'id': event_id,
            'name': name,
            'channel_id': channel_id,
            'message_id': message_id,
            'creator_id': creator_id,
            'created_at': datetime.now().isoformat(),
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
    
    def get_events_in_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all events within a date range"""
        filtered_events = []
        for event in self.events.values():
            event_date = datetime.fromisoformat(event['created_at'])
            if start_date <= event_date <= end_date:
                filtered_events.append(event)
        return filtered_events
    
    def generate_summary(self, events: List[Dict]) -> Dict:
        """Generate attendance summary for events"""
        summary = {
            'generated_at': datetime.now().isoformat(),
            'total_events': len(events),
            'events': []
        }
        
        for event in events:
            event_summary = {
                'id': event['id'],
                'name': event['name'],
                'created_at': event['created_at'],
                'total_attendees': len(event['attendance']),
                'attendance_by_user': event['attendance']
            }
            summary['events'].append(event_summary)
        
        return summary

# Initialize event tracker
event_tracker = EventTracker()

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse various timestamp formats into datetime object"""
    timestamp_str = timestamp_str.strip()
    
    # Try epoch timestamp first (numeric)
    if timestamp_str.isdigit():
        try:
            epoch_seconds = int(timestamp_str)
            return datetime.fromtimestamp(epoch_seconds)
        except (ValueError, OSError):
            pass
    
    # Try full timestamp format: YYYY-MM-DD HH:MM:SS
    try:
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    
    # Try date only format: YYYY-MM-DD
    try:
        return datetime.strptime(timestamp_str, '%Y-%m-%d')
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
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse timestamp: {timestamp_str}. Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, epoch seconds")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

@bot.command(name='create_event')
async def create_event(ctx, *, event_name: str):
    """Create a new event"""
    if EVENT_CHANNEL_ID and ctx.channel.id != EVENT_CHANNEL_ID:
        await ctx.send(f"Events can only be created in the designated event channel.")
        return
    
    # Generate unique event ID
    event_id = f"{ctx.message.id}_{int(datetime.now().timestamp())}"
    
    # Create event
    event = event_tracker.create_event(
        event_id=event_id,
        name=event_name,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id,
        creator_id=ctx.author.id
    )
    
    # Send event message
    embed = discord.Embed(
        title=f"🎉 Event: {event_name}",
        description=f"React with {DEFAULT_EMOJI} to register your attendance!",
        color=discord.Color.green()
    )
    embed.add_field(name="Created by", value=ctx.author.mention, inline=True)
    embed.add_field(name="Created at", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    embed.set_footer(text=f"Event ID: {event_id}")
    
    event_message = await ctx.send(embed=embed)
    
    # Add default emoji reaction
    await event_message.add_reaction(DEFAULT_EMOJI)
    
    # Update event with the actual message ID
    event['message_id'] = event_message.id
    event_tracker.events[event_id]['message_id'] = event_message.id

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
        start_dt = parse_timestamp(start_timestamp)
        
        # Parse end timestamp or set to current time if not provided
        if end_timestamp is None:
            end_dt = datetime.now()
        else:
            end_dt = parse_timestamp(end_timestamp)
            # If only date was provided, extend end time to end of day
            if len(end_timestamp.split()) == 1 and not end_timestamp.isdigit():
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
        
        # Get events in range
        events_in_range = event_tracker.get_events_in_range(start_dt, end_dt)
        
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
        name="Create Event",
        value=f"`{BOT_PREFIX}create_event Event Name`\nCreates a new event that users can react to",
        inline=False
    )
    
    embed.add_field(
        name="Generate Summary",
        value=f"`{BOT_PREFIX}summary START_TIMESTAMP [END_TIMESTAMP]`\nGenerates attendance summary for events in time range\n\n**Supported timestamp formats:**\n• `YYYY-MM-DD` (date only)\n• `YYYY-MM-DD HH:MM:SS` (full timestamp)\n• `YYYY-MM-DD HH:MM` (date with time)\n• `YYYY/MM/DD` (alternative format)\n• `MM/DD/YYYY` (US format)\n• `1234567890` (epoch seconds)\n\n**Examples:**\n• `{BOT_PREFIX}summary 2024-01-01` (all events after Jan 1)\n• `{BOT_PREFIX}summary 2024-01-01 2024-01-31` (events in January)\n• `{BOT_PREFIX}summary 2024-01-01 09:00:00 2024-01-01 18:00:00` (events on Jan 1, 9am-6pm)\n• `{BOT_PREFIX}summary 1704067200` (all events after epoch timestamp)",
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

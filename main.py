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
    
    def add_attendance(self, event_id: str, user_id: int, emoji: str) -> bool:
        """Add attendance record for a user"""
        if event_id in self.events:
            if user_id not in self.events[event_id]['attendance']:
                self.events[event_id]['attendance'][user_id] = []
            if emoji not in self.events[event_id]['attendance'][user_id]:
                self.events[event_id]['attendance'][user_id].append(emoji)
            return True
        return False
    
    def remove_attendance(self, event_id: str, user_id: int, emoji: str) -> bool:
        """Remove attendance record for a user"""
        if event_id in self.events and user_id in self.events[event_id]['attendance']:
            if emoji in self.events[event_id]['attendance'][user_id]:
                self.events[event_id]['attendance'][user_id].remove(emoji)
                if not self.events[event_id]['attendance'][user_id]:
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
        event_tracker.add_attendance(event_id, user.id, emoji_str)
        print(f"Added attendance: User {user.name} ({user.id}) reacted with {emoji_str} to event {event_id}")

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
        event_tracker.remove_attendance(event_id, user.id, emoji_str)
        print(f"Removed attendance: User {user.name} ({user.id}) removed {emoji_str} from event {event_id}")

@bot.command(name='summary')
async def generate_summary(ctx, start_date: str, end_date: str):
    """Generate attendance summary for events in a date range"""
    try:
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include the end date
        
        # Get events in range
        events_in_range = event_tracker.get_events_in_range(start_dt, end_dt)
        
        if not events_in_range:
            await ctx.send(f"No events found in the date range {start_date} to {end_date}")
            return
        
        # Generate summary
        summary = event_tracker.generate_summary(events_in_range)
        
        # Send summary as JSON (for programmatic use)
        summary_json = json.dumps(summary, indent=2)
        
        # Create embed for display
        embed = discord.Embed(
            title="📊 Event Attendance Summary",
            description=f"Events from {start_date} to {end_date}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Total Events", 
            value=str(summary['total_events']), 
            inline=True
        )
        
        total_attendees = sum(event['total_attendees'] for event in summary['events'])
        embed.add_field(
            name="Total Attendees", 
            value=str(total_attendees), 
            inline=True
        )
        
        # Add event details
        for event in summary['events'][:5]:  # Show first 5 events
            attendees_list = []
            for user_id, emojis in event['attendance_by_user'].items():
                user = bot.get_user(int(user_id))
                username = user.name if user else f"User {user_id}"
                attendees_list.append(f"{username}: {', '.join(emojis)}")
            
            embed.add_field(
                name=f"🎉 {event['name']}",
                value=f"Attendees: {event['total_attendees']}\n" + 
                      ("\n".join(attendees_list[:3]) + ("..." if len(attendees_list) > 3 else "")),
                inline=False
            )
        
        embed.set_footer(text=f"Generated at {summary['generated_at']}")
        
        await ctx.send(embed=embed)
        
        # Send raw JSON data for programmatic use
        if len(summary_json) > 2000:
            # Split into multiple messages if too long
            chunks = [summary_json[i:i+1900] for i in range(0, len(summary_json), 1900)]
            for i, chunk in enumerate(chunks):
                await ctx.send(f"```json\n{chunk}\n```")
        else:
            await ctx.send(f"```json\n{summary_json}\n```")
            
    except ValueError as e:
        await ctx.send(f"Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}")
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
        value=f"`{BOT_PREFIX}summary YYYY-MM-DD YYYY-MM-DD`\nGenerates attendance summary for events in date range",
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

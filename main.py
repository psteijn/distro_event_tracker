import discord
from discord.ext import commands
import asyncio
import sys
from datetime import datetime, timedelta
import json
import os
import logging
import time
from typing import Dict, List, Optional
import pytz
from config import DISCORD_TOKEN, BOT_PREFIX, EVENT_CHANNEL_ID, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_FIFTY, EMOJI_TWENTY_FIVE
from reminders import handle_event_reminder

# Logging configuration
log_file = os.getenv('LOG_FILE', 'bot.log')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
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
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

# In-memory storage for events (will be replaced with database later)
events_storage = {}

# Global emoji cache - loaded once at startup
hundred_emoji = None
seventy_five_emoji = None
fifty_emoji = None
twenty_five_emoji = None

def generate_single_event_summary(event: Dict) -> discord.Embed:
    """Generate a detailed summary embed for a single event"""
    embed = discord.Embed(
        title=f"📊 Event Summary: {event['name']}",
        color=discord.Color.blue()
    )
    
    # Add event details
    embed.add_field(
        name="Event ID",
        value=event['id'],
        inline=True
    )
    
    # Format creation time
    created_time = datetime.fromtimestamp(event['created_at'], tz=PACIFIC_TZ)
    created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')
    
    embed.add_field(
        name="Created",
        value=created_time_str,
        inline=True
    )
    
    # Get creator name
    creator_name = "Unknown"
    try:
        # Try to get the creator from the bot's user cache
        creator = bot.get_user(event['creator_id'])
        if creator:
            creator_name = creator.name
    except:
        pass
    
    embed.add_field(
        name="Created by",
        value=creator_name,
        inline=True
    )
    
    # Process attendance
    total_attendees = len(event['attendance']) + len(event.get('manual_attendance', []))
    embed.add_field(
        name="Total Attendees",
        value=str(total_attendees),
        inline=True
    )
    
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
            chunks = [attendance_text[i:i+20] for i in range(0, len(attendance_text), 20)]
            for i, chunk in enumerate(chunks):
                field_name = f"Attendees (Part {i+1})" if len(chunks) > 1 else "Attendees"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )
        else:
            embed.add_field(
                name="Attendees",
                value="\n".join(attendance_text),
                inline=False
            )
    else:
        embed.add_field(
            name="Attendees",
            value="No attendees yet",
            inline=False
        )
    
    # Add weighted score calculation
    if event['attendance'] or event.get('manual_attendance'):
        weighted_scores = calculate_event_weighted_scores(event)
        if weighted_scores:
            score_text = []
            for user_name, score in weighted_scores.items():
                score_str = f"{score:.2f}".rstrip('0').rstrip('.')
                score_text.append(f"{user_name}: {score_str}")
            
            embed.add_field(
                name="Weighted Scores",
                value="\n".join(score_text),
                inline=False
            )
    
    embed.set_footer(text=f"Event ID: {event['id']}")
    embed.timestamp = datetime.now(PACIFIC_TZ)
    
    return embed

def calculate_event_weighted_scores(event: Dict) -> Dict[str, float]:
    """Calculate weighted scores for attendees of a single event"""
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
    text_output = f"📊 Event Attendance Summary\n"
    text_output += f"Event: {event['name']}\n"
    text_output += f"Created: {created_time_str}\n"
    text_output += f"Total Attendees: {len(event['attendance']) + len(event.get('manual_attendance', []))}\n\n"
    
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
    def __init__(self):
        self.events = {}
    
    def create_event(self, event_id: str, name: str, channel_id: int, message_id: int, creator_id: int, created_at: float, multiplier: float = 1.0, type_emoji: str = "", is_historical: bool = False) -> Dict:
        """Create a new event with a multiplier for scoring"""
        event = {
            'id': event_id,
            'name': name,
            'type_emoji': type_emoji,
            'channel_id': channel_id,
            'message_id': message_id,
            'creator_id': creator_id,
            'created_at': created_at,
            'multiplier': multiplier,
            'attendance': {},
            'manual_attendance': [],
            'is_historical': is_historical
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
        
        # Always return sorted by time
        return sorted(filtered_events, key=lambda x: x['created_at'])

    def get_events_between_ids(self, start_id: str, end_id: str) -> List[Dict]:
        """Get all events between two specific IDs (inclusive)"""
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
            return all_events[s:e+1]
        
        return []

    def get_last_n_events(self, n: int) -> List[Dict]:
        """Get the most recent N events"""
        all_events = sorted(self.events.values(), key=lambda x: x['created_at'], reverse=True)
        return sorted(all_events[:n], key=lambda x: x['created_at'])
    
    def get_most_recent_before(self, event_id: str) -> Optional[Dict]:
        """Find the most recent event created before the given event ID"""
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
            'events': []
        }
        
        for event in events:
            # Ensure manual_attendance key exists (defensive coding for existing events)
            if 'manual_attendance' not in event:
                event['manual_attendance'] = []
            
            total_attendees = len(event['attendance']) + len(event['manual_attendance'])
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
                'attendance_by_user': attendance_by_user
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
                
                # Early filtering: Skip non-bot messages immediately
                if message.author != bot.user:
                    continue
                
                # Early filtering: Skip messages without embeds
                if not message.embeds:
                    continue
                
                event_messages_found += 1
                
                if await self._process_message_for_events(message, is_historical=True):
                    reconstructed_count += 1
        else:
            logger.error(f"❌ Channel {EVENT_CHANNEL_ID} not found")

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        logger.info(f"✅ Reconstructed {reconstructed_count} events from {event_messages_found} event messages (scanned {total_messages_scanned} total messages) in {duration:.2f} seconds")
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
                            elif emoji_str == str(seventy_five_emoji) or EMOJI_SEVENTY_FIVE in emoji_str:
                                multiplier = 0.75
                            elif emoji_str == str(fifty_emoji) or EMOJI_FIFTY in emoji_str:
                                multiplier = 0.5
                            elif emoji_str == str(twenty_five_emoji) or EMOJI_TWENTY_FIVE in emoji_str:
                                multiplier = 0.25
                            manual_attendance_users.append({'name': user_name, 'multiplier': multiplier})
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
            'is_historical': is_historical
        }
        
        # Process reactions to get attendance
        await self._process_reactions_for_event(event, message)
        
        # Store the event
        self.events[event_id] = event
        attendance_user_list = [user[0] for user in event['attendance'].values()] + manual_attendance_users
        logger.info(f"📝 Reconstructed event: {event_name} (ID: {event_id}, multiplier: {embed_multiplier}x, attendance: {attendance_user_list})")
        return True
    
    async def _process_reactions_for_event(self, event, message):
        """Process reactions on a message to reconstruct attendance with parallel processing"""
        try:
            # Optimization #2: Parallel reaction processing
            # Collect all reaction tasks first
            reaction_tasks = []
            
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji)
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

@bot.event
async def on_ready():
    global hundred_emoji, seventy_five_emoji, fifty_emoji, twenty_five_emoji
    
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
                logger.info(f"✅ Successfully loaded all emojis: {EMOJI_HUNDRED}, {EMOJI_SEVENTY_FIVE}, {EMOJI_FIFTY}, {EMOJI_TWENTY_FIVE}")
        else:
            logger.error("❌ No guilds found - emojis cannot be loaded")
    except Exception as e:
        logger.error(f"❌ Error loading emojis: {e}")
    
    # Reconstruct events from message history
    try:
        reconstructed_count = await event_tracker.reconstruct_from_history(bot)
        logger.info(f'🚀 Bot ready! Reconstructed {reconstructed_count} events from history.')
    except Exception as e:
        logger.error(f'❌ Error during event reconstruction: {e}')
        logger.info('🚀 Bot ready! (Running without historical events)')

async def create_event_with_multiplier(ctx, event_name: str, multiplier: float, emoji: str, color: discord.Color):
    """Helper function to create events with multipliers"""
    if EVENT_CHANNEL_ID and str(ctx.channel.id) != EVENT_CHANNEL_ID:
        await ctx.send(f"Events can only be created in the designated event channel.")
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
        multiplier=multiplier
    )
    
    # Send event message
    embed = discord.Embed(
        title=f"{emoji} {event_name}",
        description=f"React with {hundred_emoji} {seventy_five_emoji} {fifty_emoji} {twenty_five_emoji} to register your attendance!\n{hundred_emoji} is full attendance, the others are partial attendance.",
        color=color
    )
    embed.add_field(name="Created by", value=ctx.author.mention, inline=True)
    
    # Format creation time
    created_time_str = created_time.strftime('%Y-%m-%d %H:%M:%S')
    embed.add_field(name="📊Summary", value=f"`!summary {event_id}`", inline=True)
    embed.set_footer(text=f"Event ID: {event_id}")
    
    event_message = await ctx.send(embed=embed)

    # Update event with the actual message ID
    # NOTE: do this before the reactions below, otherwise fast clicking users can react before these
    # lines execute.
    event['message_id'] = event_message.id
    event_tracker.events[event_id]['message_id'] = event_message.id

    await event_message.add_reaction(twenty_five_emoji)
    await event_message.add_reaction(fifty_emoji)
    await event_message.add_reaction(seventy_five_emoji)
    await event_message.add_reaction(hundred_emoji)
    
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
            event['manual_attendance'] = [user for user in event['manual_attendance'] if user['name'] != member_name]
            # Add user with new multiplier
            event['manual_attendance'].append({'name': member_name, 'multiplier': multiplier})
        
        # Update the original event message to show the new attendance
        try:
            channel = bot.get_channel(event['channel_id'])
            if not channel:
                await ctx.send(f"❌ Channel with ID `{event['channel_id']}` not found.")
                return

            event_message = await channel.fetch_message(event['message_id'])
            
            # Create updated embed
            embed = event_message.embeds[0]

            # Create the manual attendance display string with emojis
            manual_attendance_display = []
            for user_data in event['manual_attendance']:
                if isinstance(user_data, dict):
                    # New format with emoji based on multiplier
                    emoji_string = multiplier_to_emoji_string(user_data['multiplier'])
                    manual_attendance_display.append(f"{emoji_string} {user_data['name']}")
                else:
                    # Old format (shouldn't happen after conversion, but safety check)
                    manual_attendance_display.append(str(user_data))

            found_existing_field = False
            for index, field in enumerate(embed.fields):
               if field.name == "Manual Attendance":
                    # Replace the field with updated manual attendance
                    embed.set_field_at(index, name=field.name, value=', '.join(manual_attendance_display), inline=field.inline)
                    found_existing_field = True
                    break
            if not found_existing_field:
                embed.add_field(name="Manual Attendance", value=', '.join(manual_attendance_display), inline=True)

            # Update the embed
            await event_message.edit(embed=embed)

            # Re-process the message to update the event
            await event_tracker._process_message_for_events(event_message)

            # Send confirmation
            await ctx.send(f"✅ Successfully added {len(member_names)} user(s) to event with {multiplier}x multiplier: {', '.join(member_names)}")
            print(f"Added users to event {event_id}: {', '.join(member_names)} with {multiplier}x multiplier by {ctx.author.name}")
                
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
            "Please use the correct format: `!add_users <event_id> <multiplier> <user_names>`\n"
            "**Example:** `!add_users 1424971912928563281_1759810178 0.75 @Beetle @Mantis`\n"
            "**Fixed Multipliers:** 1.0 (full), 0.75 (partial), 0.5 (half), 0.25 (quarter)"
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
async def summary(ctx, *, args: str = ""):
    """Generate attendance summary for events
    
    Usage:
    !summary EVENT_ID - Summary for a single event
    !summary ID1 ID2 - Summary for range of events (inclusive)
    !summary last N - Summary for the last N events
    !summary YYYY-MM-DD [YYYY-MM-DD] - Summary for date range
    """
    try:
        events_to_summarize = []
        arg_list = args.split()
        
        # 1. Handle "last N"
        if len(arg_list) >= 2 and arg_list[0].lower() == "last":
            try:
                n = int(arg_list[1])
                events_to_summarize = event_tracker.get_last_n_events(n)
                summary_title = f"Last {len(events_to_summarize)} Events"
            except ValueError:
                await ctx.send("❌ Please provide a number for 'last'. Example: `!summary last 5`.")
                return

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
                    return

        # 3. Handle Timestamps (Legacy/Fallback)
        elif len(arg_list) > 0:
            try:
                # Attempt to parse as start [end] timestamps
                # This is greedy and handles spaces/quotes poorly in basic split, 
                # but we'll try to find at least one valid date.
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
                summary_title = f"Range: {arg_list[0]}" + (f" to {arg_list[1]}" if len(arg_list) >= 2 else " onwards")
                
            except ValueError:
                await ctx.send("❌ Could not parse input. Use `!summary help` for usage info.")
                return
        
        else:
            # No args - default to last event
            events_to_summarize = event_tracker.get_last_n_events(1)
            summary_title = "Latest Event"

        if not events_to_summarize:
            await ctx.send("❌ No events found for the specified criteria.")
            return

        # Generate summary
        summary_data = event_tracker.generate_summary(events_to_summarize)
        
        # Create verification header
        first_event = events_to_summarize[0]
        last_event = events_to_summarize[-1]
        
        text_output = f"📊 Event Attendance Summary\n"
        text_output += f"Context: {summary_title}\n"
        text_output += f"Range: {first_event['name']} -> {last_event['name']}\n"
        text_output += f"Total Events: {len(events_to_summarize)}\n\n"
        
        # Add event details
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
                text_output += f"{line_header}: {', '.join(attendees_list)}\n"
            else:
                text_output += f"{line_header}: (no attendees)\n"
        
        # Add event names line for easy auditing
        event_names = [event['name'] for event in summary_data['events']]
        text_output += f"\n-------\nEvents: {', '.join(event_names)}\n"
        
        # Add weighted average summary
        weighted_summary = event_tracker.calculate_weighted_average(summary_data['events'])
        text_output += f"{weighted_summary}\n"
        
        # Send output
        if len(text_output) > 2000:
            chunks = [text_output[i:i+1900] for i in range(0, len(text_output), 1900)]
            for chunk in chunks:
                await ctx.send(f"```\n{chunk}\n```")
        else:
            await ctx.send(f"```\n{text_output}\n```")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        logger.error(f"Error in summary command: {e}")

@bot.command(name='delete_event')
async def delete_event(ctx, event_id: str):
    """Delete an event (only the event creator can delete their own events)
    
    Usage: !delete_event EVENT_ID
    """
    try:
        # Check if event exists
        if event_id not in event_tracker.events:
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return
        
        event = event_tracker.events[event_id]
        
        # Check if user is the event creator
        if event['creator_id'] != ctx.author.id:
            await ctx.send(f"❌ You can only delete events that you created. This event was created by someone else.")
            return
        
        # Send confirmation message
        confirmation_embed = discord.Embed(
            title="⚠️ Confirm Event Deletion",
            description=f"Are you sure you want to delete the event **{event['name']}**?\n\nThis action cannot be undone and will remove all attendance data.",
            color=discord.Color.red()
        )
        confirmation_embed.add_field(name="Event ID", value=event_id, inline=True)
        confirmation_embed.add_field(name="Created", value=f"<t:{int(event['created_at'])}:R>", inline=True)
        confirmation_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
        
        confirmation_message = await ctx.send(embed=confirmation_embed)
        
        # Add reaction buttons
        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ["✅", "❌"] and 
                   reaction.message.id == confirmation_message.id)
        
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
                            print(f"Warning: Could not delete Discord message for event {event_id}: {e}")
                    
                    # Remove from memory
                    del event_tracker.events[event_id]
                    
                    # Send success message
                    success_embed = discord.Embed(
                        title="✅ Event Deleted",
                        description=f"Successfully deleted event **{event['name']}**",
                        color=discord.Color.green()
                    )
                    success_embed.add_field(name="Event ID", value=event_id, inline=True)
                    await ctx.send(embed=success_embed)
                    
                    # Log the deletion
                    print(f"🗑️ Event deleted: {event['name']} (ID: {event_id}) by {ctx.author.name} ({ctx.author.id})")
                    
                except Exception as e:
                    await ctx.send(f"❌ An error occurred while deleting the event: {str(e)}")
                    print(f"Error deleting event {event_id}: {e}")
                    
            elif str(reaction.emoji) == "❌":
                # User cancelled deletion
                await ctx.send("❌ Event deletion cancelled.")
                
        except asyncio.TimeoutError:
            await ctx.send("⏰ Deletion confirmation timed out. Event was not deleted.")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        print(f"Error in delete_event command: {e}")

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
        print(f"An unhandled error in delete_event occurred: {error}")

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
                await ctx.send("❌ Need at least 2 events to compare. Only found {len(events)} event(s).")
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
            await ctx.send("❌ Please provide either no parameters (for last two events) or both event IDs.")
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
                color=discord.Color.orange()
            )
            
            # Split into chunks if too many users
            if len(missing_list) > 20:
                chunks = [missing_list[i:i+20] for i in range(0, len(missing_list), 20)]
                for i, chunk in enumerate(chunks):
                    field_name = f"Missing Users (Part {i+1})" if len(chunks) > 1 else "Missing Users"
                    embed.add_field(
                        name=field_name,
                        value=", ".join(chunk),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Missing Users",
                    value=", ".join(missing_list),
                    inline=False
                )
            
            embed.add_field(
                name="Summary",
                value=f"**{len(missing_users)}** user(s) attended the previous event but missed the recent one",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        else:
            # No missing users
            embed = discord.Embed(
                title="✅ All Previous Attendees Present",
                description=f"Everyone who attended **{event2_name}** also attended **{event1_name}**!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Summary",
                value=f"**{len(event2_attendees)}** user(s) attended both events",
                inline=False
            )
            await ctx.send(embed=embed)
        
        print(f"Missing command used by {ctx.author.name}: {len(missing_users)} users missing from {event1_name} who attended {event2_name}")
        
    except Exception as e:
        await ctx.send(f"❌ An error occurred while checking missing users: {str(e)}")
        print(f"Error in missing command: {e}")

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
        print(f"An unhandled error in missing command occurred: {error}")

@bot.command(name='rename', aliases=['rename_event'])
async def rename_event(ctx, event_id: str, *, new_name: str):
    """Rename an event (only the event creator can rename their own events)
    
    Usage: !rename EVENT_ID NEW_NAME
    Example: !rename 1424971912928563281_1759810178 "New Event Name"
    """
    try:
        # Check if event exists
        if event_id not in event_tracker.events:
            await ctx.send(f"❌ Event with ID `{event_id}` not found.")
            return
        
        event = event_tracker.events[event_id]
        
        # Check if user is the event creator
        if event['creator_id'] != ctx.author.id:
            await ctx.send(f"❌ You can only rename events that you created. This event was created by someone else.")
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
                color=discord.Color.green()
            )
            success_embed.add_field(name="Event ID", value=event_id, inline=True)
            success_embed.add_field(name="Old Name", value=old_name, inline=True)
            success_embed.add_field(name="New Name", value=new_name, inline=True)
            
            await ctx.send(embed=success_embed)
            
            # Log the rename
            print(f"🔄 Event renamed: {old_name} → {new_name} (ID: {event_id}) by {ctx.author.name} ({ctx.author.id})")
            
        except discord.NotFound:
            await ctx.send(f"❌ The original event message was not found. The event data has been updated in memory, but the Discord message could not be updated.")
            print(f"⚠️ Event message not found for rename: {event_id}")
        except Exception as e:
            await ctx.send(f"❌ An error occurred while updating the Discord message: {str(e)}")
            print(f"Error updating Discord message for rename: {e}")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred while renaming the event: {str(e)}")
        print(f"Error in rename_event command: {e}")

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
        print(f"An unhandled error in rename_event occurred: {error}")

@bot.command(name='help_events')
async def help_events(ctx):
    """Show help for event commands"""
    embed = discord.Embed(
        title="🤖 Event Tracker Bot Commands",
        description="Commands for managing events and attendance tracking with weighted scoring",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📅 Create Events",
        value=f"`{BOT_PREFIX}dungeon Dungeon Name` - 🏰 Dungeon (1x multiplier)\n`{BOT_PREFIX}miniboss Miniboss Name` - ⚔️ Miniboss (1x multiplier)\n`{BOT_PREFIX}mini Miniboss Name` - ⚔️ Miniboss (1x multiplier, alias)\n`{BOT_PREFIX}t8 T8 Name` - 🗺️ T8 Maps (1x multiplier)\n`{BOT_PREFIX}boss Boss Name` - 👹 Boss (2x multiplier)\n`{BOT_PREFIX}main Boss Name` - 👹 Boss (2x multiplier, alias)\n`{BOT_PREFIX}mainboss Boss Name` - 👹 Boss (2x multiplier, alias)\n`{BOT_PREFIX}omniboss Omniboss Name` - 👑 Omniboss (8x multiplier)\n`{BOT_PREFIX}omni Omniboss Name` - 👑 Omniboss (8x multiplier, alias)\n\nCreates events with different multipliers that affect final scoring. Omniboss events give 8x points!",
        inline=False
    )
    
    embed.add_field(
        name="📊 Generate Summary",
        value=f"`{BOT_PREFIX}summary ID1 ID2` - Summary for range of events (inclusive)\n`{BOT_PREFIX}summary EVENT_ID` - Detailed summary for single event\n`{BOT_PREFIX}summary last N` - Summary for the last N events\n`{BOT_PREFIX}summary YYYY-MM-DD` - Summary for a specific date\n\n**Examples:**\n• `{BOT_PREFIX}summary last 5` (Summary of last 5 runs)\n• `{BOT_PREFIX}summary 123_456 123_789` (ID range summary)\n• `{BOT_PREFIX}summary 2024-01-01` (Everything from Jan 1 onwards)\n\nThis command identifies exactly which events are included in the output header for verification.",
        inline=False
    )
    
    embed.add_field(
        name="👥 Add Users to Event",
        value=f"`{BOT_PREFIX}add_users EVENT_ID MULTIPLIER @user1 @user2 @user3`\nManually add users to an existing event with fixed multiplier scoring\n\n**Examples:**\n• `{BOT_PREFIX}add_users 1234567890_1234567890 1.0 @alice @bob` (full attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.75 @charlie` (partial attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.5 @david` (half attendance)\n• `{BOT_PREFIX}add_users 1234567890_1234567890 0.25 @eve` (quarter attendance)\n\n**Fixed Multipliers:** 1.0 (full), 0.75 (partial), 0.5 (half), 0.25 (quarter). Updates the original event message automatically.",
        inline=False
    )

    embed.add_field(
        name="🗑️ Delete Event",
        value=f"`{BOT_PREFIX}delete_event EVENT_ID`\nDelete an event (only the event creator can delete their own events)\n\n**Example:**\n• `{BOT_PREFIX}delete_event 1234567890_1234567890`\n\n⚠️ **Warning:** This action cannot be undone and will remove all attendance data!",
        inline=False
    )

    embed.add_field(
        name="👥 Find Missing Users",
        value=f"`{BOT_PREFIX}missing [EVENT_ID1 EVENT_ID2]`\nFind users who attended one event but missed another\n\n**Examples:**\n• `{BOT_PREFIX}missing` - Compare last two events\n• `{BOT_PREFIX}missing 1234567890_1234567890 1234567890_1234567891` - Compare specific events\n\nShows users who attended the second event but missed the first event.",
        inline=False
    )

    embed.add_field(
        name="🔄 Rename Event",
        value=f"`{BOT_PREFIX}rename EVENT_ID NEW_NAME`\nRename an event (only the event creator can rename their own events)\n\n**Examples:**\n• `{BOT_PREFIX}rename 1234567890_1234567890 \"Updated Event Name\"`\n• `{BOT_PREFIX}rename_event 1234567890_1234567890 \"New Name\"`\n\nUpdates both the Discord message and the event data in memory.",
        inline=False
    )

    embed.add_field(
        name="🎯 Attendance & Scoring",
        value="**Emoji Reactions (Custom Emojis):**\n• `share_100` - 100% attendance (1.0x)\n• `share_75` - 75% attendance (0.75x)\n• `share_50` - 50% attendance (0.5x)\n• `share_25` - 25% attendance (0.25x)\n\n**Manual Attendance:**\n• Added via `add_users` command with fixed multipliers\n• Only supports: 1.0, 0.75, 0.5, 0.25\n• Example: `!add_users EVENT_ID 0.75 @user` gives 0.75x participation\n\n**Final Score = Event Multiplier × Participation Multiplier**\n• Dungeon/Miniboss/T8: 1x multiplier\n• Boss events: 2x multiplier\n• Omniboss events: 8x multiplier",
        inline=False
    )

    embed.add_field(
        name="❓ Help",
        value=f"`{BOT_PREFIX}help_events`\nShows this help message",
        inline=False
    )
    
    embed.add_field(
        name="📧 Get Event Summary in DM",
        value="Every event message now includes a **📊 Get Summary in DM** button. Click it to receive a detailed summary of that specific event in your DMs, including:\n• Complete attendee list with emoji reactions\n• Individual weighted scores for each participant\n• Event details (creator, multiplier, creation time)\n• Manual attendance entries\n\nPerfect for getting detailed info without cluttering the channel!",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ How to Attend",
        value="React to event messages with the custom emoji reactions to register your attendance level. The bot automatically tracks and calculates weighted scores across all events!",
        inline=False
    )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error("Error: DISCORD_TOKEN not found in environment variables")
        logger.error("Please create a .env file with your Discord bot token")
        sys.exit(1)
    
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

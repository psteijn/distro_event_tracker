import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Bot Settings
BOT_PREFIX = '!'
EVENT_CHANNEL_ID = None  # Set this to your specific channel ID
DEFAULT_EMOJI = '✅'  # Default emoji for attendance

# Database settings (for future SQLite implementation)
DATABASE_PATH = 'events.db'

# Summary format settings
SUMMARY_DATE_FORMAT = '%Y-%m-%d'
SUMMARY_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

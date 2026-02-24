import os
from dotenv import load_dotenv

# Load environment variables
# Check if a specific environment file is requested
env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(dotenv_path=env_file)

# Discord Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Bot Settings
BOT_PREFIX = '!'
EVENT_CHANNEL_ID = os.getenv('EVENT_CHANNEL_ID')
EMOJI_HUNDRED = 'share_100'
EMOJI_SEVENTY_FIVE = 'share_75'
EMOJI_FIFTY = 'share_50'
EMOJI_TWENTY_FIVE = 'share_25'

# Summary format settings
SUMMARY_DATE_FORMAT = '%Y-%m-%d'
SUMMARY_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

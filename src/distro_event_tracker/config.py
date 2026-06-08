import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
# Check if a specific environment file is requested
env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(dotenv_path=env_file)

# Discord Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Admin IDs - list of user IDs who have administrative privileges (e.g., delete any event)
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Bot Settings
BOT_PREFIX = '!'
EVENT_CHANNEL_ID = os.getenv('EVENT_CHANNEL_ID')
EVENT_COMMAND_NAME_PATTERN = re.compile(r"[a-z0-9_-]{1,32}")


def validate_event_command_name(name: str) -> str:
    """Validate a configured Discord slash-command name."""
    if not EVENT_COMMAND_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "EVENT_COMMAND_NAME must be 1-32 characters using only lowercase letters, "
            "numbers, hyphens, or underscores."
        )
    return name


EVENT_COMMAND_NAME = validate_event_command_name(os.getenv('EVENT_COMMAND_NAME', 'distro'))
DIBS_CHANNEL_ID = os.getenv('DIBS_CHANNEL_ID')
ITEMS_CSV = os.getenv('ITEMS_CSV', 'items.csv')
REMINDER_OPT_OUT_FILE = os.getenv('REMINDER_OPT_OUT_FILE', 'reminders_opt_out.txt')
EMOJI_HUNDRED = 'share_100'
EMOJI_SEVENTY_FIVE = 'share_75'
EMOJI_FIFTY = 'share_50'
EMOJI_TWENTY_FIVE = 'share_25'

# Summary format settings
SUMMARY_DATE_FORMAT = '%Y-%m-%d'
SUMMARY_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


@dataclass(frozen=True)
class Settings:
    """Typed runtime configuration used by new package modules."""

    discord_token: str | None
    bot_prefix: str
    event_channel_id: str | None
    event_command_name: str
    dibs_channel_id: str | None
    items_csv: Path
    reminder_opt_out_file: Path
    admin_ids: tuple[int, ...]


def load_settings() -> Settings:
    """Build settings from the environment loaded by this module."""
    return Settings(
        discord_token=DISCORD_TOKEN,
        bot_prefix=BOT_PREFIX,
        event_channel_id=EVENT_CHANNEL_ID,
        event_command_name=EVENT_COMMAND_NAME,
        dibs_channel_id=DIBS_CHANNEL_ID,
        items_csv=Path(ITEMS_CSV),
        reminder_opt_out_file=Path(REMINDER_OPT_OUT_FILE),
        admin_ids=tuple(ADMIN_IDS),
    )

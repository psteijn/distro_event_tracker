
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from reminders import handle_event_reminder
from main import EventTracker

@pytest.fixture
def tracker():
    return EventTracker()

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.get_channel = MagicMock()
    bot.get_user = MagicMock()
    bot.fetch_user = AsyncMock()
    return bot

@pytest.mark.asyncio
async def test_reminder_skipped_if_no_previous_event(mock_bot, tracker):
    """If there is no previous event, logic should exit early."""
    new_event = tracker.create_event("new", "New", 1, 100, 1, 5000.0, type_emoji="🏰")
    
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_reminder_skipped_if_outside_2_hour_window(mock_bot, tracker):
    """If the gap is > 7200s, logic should exit early."""
    # Event 1: 10:00 AM
    tracker.create_event("old", "Old", 1, 50, 1, 1000.0, type_emoji="🏰")
    # Event 2: 1:00 PM (3 hours later)
    new_event = tracker.create_event("new", "New", 1, 100, 1, 1000.0 + 10800, type_emoji="🏰")
    
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        # Should not sleep for the 120s wait
        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_reminder_identifies_missing_users_and_includes_creator(mock_bot, tracker):
    """
    Scenario: 
    - Prev Event: User 10, User 20 reacted.
    - New Event: Created by User 10. User 30 reacted.
    - Expectation: User 10 (creator) and User 20 should both be reminded if they haven't reacted.
    """
    # Prev event
    prev = tracker.create_event("old", "Old", 1, 50, 2, 1000.0, type_emoji="🏰")
    tracker.add_attendance("old", 10, "Alice", "X")
    tracker.add_attendance("old", 20, "Bob", "X")
    
    # New event (created by Alice/10)
    # Use a recent timestamp to pass the age check
    new_event = tracker.create_event("new", "New", 1, 100, 10, 2000.0, type_emoji="🏰")
    tracker.add_attendance("new", 30, "Charlie", "X") # Charlie reacted early
    
    # Mock channel and message for jump link
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    
    # Mock reactions (only Charlie reacted to new event)
    mock_reaction = MagicMock()
    mock_user_30 = MagicMock()
    mock_user_30.bot = False
    mock_user_30.id = 30
    
    async def mock_users():
        yield mock_user_30
        
    mock_reaction.users = mock_users
    mock_message.reactions = [mock_reaction]
    
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)
    mock_bot.get_channel.return_value = mock_channel
    
    # Mock users for DM
    mock_user_10 = AsyncMock()
    mock_user_10.bot = False
    mock_user_10.name = "Alice"
    
    mock_user_20 = AsyncMock()
    mock_user_20.bot = False
    mock_user_20.name = "Bob"
    
    mock_bot.get_user.side_effect = lambda uid: {10: mock_user_10, 20: mock_user_20}.get(uid)

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
         patch('reminders.datetime') as mock_datetime:
        
        # Mock current time to be close to new_event
        mock_datetime.now.return_value.timestamp.return_value = 2005.0
        
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        
        # Verify 120s wait happened
        mock_sleep.assert_any_call(120)
        
        # Verify DM sent to both Alice (creator) and Bob
        assert mock_user_10.send.call_count == 1
        assert mock_user_20.send.call_count == 1

@pytest.mark.asyncio
async def test_reminder_skipped_if_historical(mock_bot, tracker):
    """If the event is marked as historical, logic should exit early."""
    new_event = tracker.create_event("hist", "Historical", 1, 100, 1, 5000.0, type_emoji="🏰", is_historical=True)
    
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_reminder_throttles_dms(mock_bot, tracker):
    """Verify that we sleep between DMs to avoid rate limits."""
    tracker.create_event("old", "Old", 1, 50, 5, 1000.0, type_emoji="🏰")
    tracker.add_attendance("old", 1, "User1", "X")
    tracker.add_attendance("old", 2, "User2", "X")
    
    new_event = tracker.create_event("new", "New", 1, 100, 10, 2000.0, type_emoji="🏰")
    
    # Setup mocks
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    mock_message.reactions = [] # No one reacted
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)
    mock_bot.get_channel.return_value = mock_channel
    
    u1, u2 = AsyncMock(), AsyncMock()
    u1.bot = u2.bot = False
    mock_bot.get_user.side_effect = lambda uid: {1: u1, 2: u2}.get(uid)

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
         patch('reminders.datetime') as mock_datetime:
        
        # Mock current time to be close to new_event (2000.0)
        mock_datetime.now.return_value.timestamp.return_value = 2005.0
        
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        
        # Should sleep 120s once, and 1.0s twice (once for each user)
        # Total 3 sleeps
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(120)
        mock_sleep.assert_any_call(1.0)

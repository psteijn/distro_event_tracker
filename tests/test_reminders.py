
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
    new_event = tracker.create_event("new", "New", 1, 100, 1, 5000.0)
    
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_reminder_skipped_if_outside_2_hour_window(mock_bot, tracker):
    """If the gap is > 7200s, logic should exit early."""
    # Event 1: 10:00 AM
    tracker.create_event("old", "Old", 1, 50, 1, 1000.0)
    # Event 2: 1:00 PM (3 hours later)
    new_event = tracker.create_event("new", "New", 1, 100, 1, 1000.0 + 10800)
    
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        # Should not sleep for the 120s wait
        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_reminder_identifies_missing_users_and_excludes_creator(mock_bot, tracker):
    """
    Scenario: 
    - Prev Event: User 10, User 20 reacted.
    - New Event: Created by User 10. User 30 reacted.
    - Expectation: User 20 should be reminded. User 10 (creator) and User 30 (already reacted) ignored.
    """
    # Prev event
    prev = tracker.create_event("old", "Old", 1, 50, 2, 1000.0)
    tracker.add_attendance("old", 10, "Alice", "X")
    tracker.add_attendance("old", 20, "Bob", "X")
    
    # New event (created by Alice/10)
    new_event = tracker.create_event("new", "New", 1, 100, 10, 2000.0)
    tracker.add_attendance("new", 30, "Charlie", "X") # Charlie reacted early
    
    # Mock channel and message for jump link
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)
    mock_bot.get_channel.return_value = mock_channel
    
    # Mock users
    mock_user_20 = AsyncMock()
    mock_user_20.bot = False
    mock_user_20.name = "Bob"
    mock_bot.get_user.side_effect = lambda uid: mock_user_20 if uid == 20 else None

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        
        # Verify 120s wait happened
        mock_sleep.assert_any_call(120)
        
        # Verify DM sent to Bob (20)
        mock_user_20.send.assert_called_once()
        
        # Verify jump link was in the DM (check embed)
        args, kwargs = mock_user_20.send.call_args
        embed = kwargs.get('embed')
        assert embed.title == "🛡️  New"
        assert "you haven't reacted yet!" in embed.description
        assert embed.fields[0].value == "[**Jump to Event & React**](http://discord/jump)"

@pytest.mark.asyncio
async def test_reminder_throttles_dms(mock_bot, tracker):
    """Verify that we sleep between DMs to avoid rate limits."""
    tracker.create_event("old", "Old", 1, 50, 5, 1000.0)
    tracker.add_attendance("old", 1, "User1", "X")
    tracker.add_attendance("old", 2, "User2", "X")
    
    new_event = tracker.create_event("new", "New", 1, 100, 10, 2000.0)
    
    # Setup mocks
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)
    mock_bot.get_channel.return_value = mock_channel
    
    u1, u2 = AsyncMock(), AsyncMock()
    u1.bot = u2.bot = False
    mock_bot.get_user.side_effect = lambda uid: {1: u1, 2: u2}.get(uid)

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        
        # Should sleep 120s once, and 1.0s twice (once for each user)
        # Total 3 sleeps
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(120)
        mock_sleep.assert_any_call(1.0)

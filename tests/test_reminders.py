from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from distro_event_tracker.bot import EventTracker
from distro_event_tracker.events.reminders import handle_event_reminder


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
    tracker.create_event("old", "Old", 1, 50, 2, 1000.0, type_emoji="🏰")
    tracker.add_attendance("old", 10, "Alice", "X")
    tracker.add_attendance("old", 20, "Bob", "X")

    # New event (created by Alice/10)
    # Use a recent timestamp to pass the age check
    new_event = tracker.create_event("new", "New", 1, 100, 10, 2000.0, type_emoji="🏰")
    tracker.add_attendance("new", 30, "Charlie", "X")  # Charlie reacted early

    # Mock channel and messages
    mock_channel = MagicMock()

    # Mock New Message
    mock_message_new = MagicMock()
    mock_message_new.jump_url = "http://discord/jump"
    mock_reaction_new = MagicMock()
    mock_user_30 = MagicMock()
    mock_user_30.bot = False
    mock_user_30.id = 30

    async def mock_users_new():
        yield mock_user_30

    mock_reaction_new.users = mock_users_new
    mock_message_new.reactions = [mock_reaction_new]

    # Mock Previous Message
    mock_message_prev = MagicMock()
    mock_reaction_prev1 = MagicMock()
    mock_reaction_prev2 = MagicMock()
    u10, u20 = MagicMock(), MagicMock()
    u10.id, u10.bot = 10, False
    u20.id, u20.bot = 20, False

    async def mock_users_p1():
        yield u10

    async def mock_users_p2():
        yield u20

    mock_reaction_prev1.users = mock_users_p1
    mock_reaction_prev2.users = mock_users_p2
    mock_message_prev.reactions = [mock_reaction_prev1, mock_reaction_prev2]

    # Helper to return different messages based on ID
    async def fake_fetch(mid):
        return mock_message_new if mid == 100 else mock_message_prev

    mock_channel.fetch_message.side_effect = fake_fetch
    mock_bot.get_channel.return_value = mock_channel

    # Mock users for DM
    mock_user_10 = AsyncMock()
    mock_user_10.bot = False
    mock_user_10.name = "Alice"

    mock_user_20 = AsyncMock()
    mock_user_20.bot = False
    mock_user_20.name = "Bob"

    mock_bot.get_user.side_effect = lambda uid: {10: mock_user_10, 20: mock_user_20}.get(uid)

    with (
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        patch('distro_event_tracker.events.reminders.datetime') as mock_datetime,
    ):

        # Mock current time to be close to new_event
        mock_datetime.now.return_value.timestamp.return_value = 2005.0

        await handle_event_reminder(mock_bot, tracker, new_event, None)

        # Verify 120s wait happened
        mock_sleep.assert_any_call(120)

        # Verify DM sent to both Alice (creator) and Bob
        assert mock_user_10.send.call_count == 1
        assert mock_user_20.send.call_count == 1

        # Verify mention is in the description
        args, kwargs = mock_user_10.send.call_args
        embed = kwargs.get('embed')
        assert "<@10>" in embed.description


@pytest.mark.asyncio
async def test_reminder_skipped_if_historical(mock_bot, tracker):
    """If the event is marked as historical, logic should exit early."""
    new_event = tracker.create_event(
        "hist", "Historical", 1, 100, 1, 5000.0, type_emoji="🏰", is_historical=True
    )

    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        await handle_event_reminder(mock_bot, tracker, new_event, None)
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_absolute_age_skip(mock_bot, tracker):
    """If the event is > 10m old, logic should exit early regardless of metadata."""
    new_event = tracker.create_event(
        "old", "Old", 1, 100, 1, 1000.0, type_emoji="🏰", is_historical=False
    )

    with (
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        patch('distro_event_tracker.events.reminders.datetime') as mock_datetime,
    ):

        # Mock current time to be 11 minutes after the event
        mock_datetime.now.return_value.timestamp.return_value = 1000.0 + 660.0

        await handle_event_reminder(mock_bot, tracker, new_event, None)
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_throttles_dms(mock_bot, tracker):
    """Verify that we sleep between DMs to avoid rate limits."""
    tracker.create_event("old", "Old", 1, 50, 5, 1000.0, type_emoji="🏰", is_historical=False)
    tracker.add_attendance("old", 1, "User1", "X")
    tracker.add_attendance("old", 2, "User2", "X")

    new_event = tracker.create_event(
        "new", "New", 1, 100, 10, 2000.0, type_emoji="🏰", is_historical=False
    )

    # Setup mocks
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    mock_message.reactions = []  # No one reacted yet

    # Mock previous message reactions
    m1, m2 = MagicMock(), MagicMock()
    u1, u2 = MagicMock(), MagicMock()
    u1.id, u1.bot = 1, False
    u2.id, u2.bot = 2, False

    async def f1():
        yield u1

    async def f2():
        yield u2

    m1.users = f1
    m2.users = f2

    mock_message_prev = MagicMock()
    mock_message_prev.reactions = [m1, m2]

    async def fake_fetch(mid):
        return mock_message if mid == 100 else mock_message_prev

    mock_channel.fetch_message.side_effect = fake_fetch
    mock_bot.get_channel.return_value = mock_channel

    udm1, udm2 = AsyncMock(), AsyncMock()
    udm1.bot = udm2.bot = False
    mock_bot.get_user.side_effect = lambda uid: {1: udm1, 2: udm2}.get(uid)

    with (
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        patch('distro_event_tracker.events.reminders.datetime') as mock_datetime,
    ):

        # Mock current time to be close to new_event (2000.0)
        mock_datetime.now.return_value.timestamp.return_value = 2005.0

        await handle_event_reminder(mock_bot, tracker, new_event, None)

        # Should sleep 120s once, and 1.0s twice (once for each user)
        # Total 3 sleeps
        assert mock_sleep.call_count == 3


@pytest.mark.asyncio
async def test_reminder_respects_opt_out(mock_bot, tracker):
    """Verify that users who have opted out are skipped by reminders."""
    # Alice (1) and Bob (2) were at the old event
    tracker.create_event("old", "Old", 1, 50, 5, 1000.0, type_emoji="🏰", is_historical=False)
    tracker.add_attendance("old", 1, "Alice", "X")
    tracker.add_attendance("old", 2, "Bob", "X")

    # Bob (2) opts out
    tracker.opted_out_users.add(2)

    new_event = tracker.create_event(
        "new", "New", 1, 100, 10, 2000.0, type_emoji="🏰", is_historical=False
    )

    # Setup mocks
    mock_channel = MagicMock()
    mock_message = MagicMock()
    mock_message.jump_url = "http://discord/jump"
    mock_message.reactions = []  # No one reacted yet

    # Mock previous message reactions
    m1, m2 = MagicMock(), MagicMock()
    u1, u2 = MagicMock(), MagicMock()
    u1.id, u1.bot = 1, False
    u2.id, u2.bot = 2, False

    async def f1():
        yield u1

    async def f2():
        yield u2

    m1.users = f1
    m2.users = f2

    mock_message_prev = MagicMock()
    mock_message_prev.reactions = [m1, m2]

    async def fake_fetch(mid):
        return mock_message if mid == 100 else mock_message_prev

    mock_channel.fetch_message.side_effect = fake_fetch
    mock_bot.get_channel.return_value = mock_channel

    u_alice, u_bob = AsyncMock(), AsyncMock()
    u_alice.id, u_alice.bot, u_alice.name = 1, False, "Alice"
    u_bob.id, u_bob.bot, u_bob.name = 2, False, "Bob"
    mock_bot.get_user.side_effect = lambda uid: {1: u_alice, 2: u_bob}.get(uid)

    with (
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        patch('distro_event_tracker.events.reminders.datetime') as mock_datetime,
    ):

        # Mock current time to be close to new_event (2000.0)
        mock_datetime.now.return_value.timestamp.return_value = 2005.0

        await handle_event_reminder(mock_bot, tracker, new_event, None)

        # Alice should be reminded, Bob should be skipped
        assert u_alice.send.call_count == 1
        assert u_bob.send.call_count == 0

        # Should sleep 120s once, and 1.0s once (only for Alice)
        assert mock_sleep.call_count == 2

# Event Reminder Logic

This feature helps maintain event momentum by reminding active participants from a previous event to react to a new one if they haven't done so within 2 minutes.

## Core Rules
1. **The 2-Hour Session Window**: A reminder is only triggered if the most recent previous event was created within the last **2 hours (7200 seconds)**. If the gap is larger, the bot assumes it's a new session and won't send DMs.
2. **The 120-Second Wait**: The bot waits exactly **120 seconds** after a new event is created before checking participation. This allows active users time to react naturally.
3. **The "Recently Active" Set**: The bot only considers users who **reacted** to the previous event. Manually added users and the creator of the new event are ignored to prevent spam.
4. **The "Missing" Delta**: A DM is only sent to users who reacted to the previous event but have *not* yet reacted to the new one.
5. **Polite Delivery**: DMs are throttled (1.0s delay) and include a direct **jump link** to the event message for easy participation.

## Technical Details
- **Trigger**: Called via `asyncio.create_task()` in `create_event_with_multiplier`.
- **Filtering**: Specifically excludes bots and the event creator.
- **Resilience**: Fetches users via `fetch_user` if they aren't in the local cache.

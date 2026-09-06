"""Private Discord menu adapter for creating a planning draft."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

import discord
import pytz

from .planning import build_blocks
from .planning_display import time_range
from .planning_draft import (
    TIMEZONES,
    PlanningDraft,
    day_choices,
    ending_choices,
    starting_choices,
)

if TYPE_CHECKING:
    from .planning_cog import PlanningCog

logger = logging.getLogger(__name__)
STEPS = ("timezone", "day", "start", "end", "preview")


class PlanningWizard(discord.ui.View):
    def __init__(
        self,
        cog: PlanningCog,
        draft: PlanningDraft,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        super().__init__(timeout=900)
        self.cog = cog
        self.draft = draft
        self.now = now
        self.last_activity = now()
        self.step = "timezone"
        self.half = "pm"
        self.revision = 0
        self.finished = False
        self.lock = asyncio.Lock()
        self.message = None
        self.render()

    def clock_label(self, instant: datetime) -> str:
        return (
            instant.astimezone(pytz.timezone(self.draft.input_timezone))
            .strftime("%I:%M %p")
            .lstrip("0")
        )

    def add_button(self, label: str, action: str, *, row: int, disabled=False, primary=False):
        revision = self.revision
        button = discord.ui.Button(
            label=label,
            row=row,
            disabled=disabled,
            style=discord.ButtonStyle.primary if primary else discord.ButtonStyle.secondary,
        )

        async def callback(interaction):
            await self.handle(interaction, action, revision=revision)

        button.callback = callback
        self.add_item(button)

    def add_select(self, placeholder: str, action: str, options: list[discord.SelectOption]):
        revision = self.revision
        select = discord.ui.Select(placeholder=placeholder, options=options, row=0)

        async def callback(interaction):
            await self.handle(interaction, action, select.values[0], revision=revision)

        select.callback = callback
        self.add_item(select)

    def render(self, notice: str = "") -> str:
        self.clear_items()
        self.revision += 1
        draft = self.draft
        zone_label = TIMEZONES[draft.input_timezone]
        header = f"**Plan: {discord.utils.escape_markdown(draft.name)}**\n"
        header += f"Choosing times in **{zone_label}**.\n"
        if self.step == "timezone":
            body = "Which timezone should we use when you pick times? Confirm Pacific or choose another."
            self.add_select(
                "Choose timezone",
                "zone",
                [
                    discord.SelectOption(
                        label=label, value=zone, default=zone == draft.input_timezone
                    )
                    for zone, label in TIMEZONES.items()
                ],
            )
            self.add_button("Continue", "continue", row=1, primary=True)
        elif self.step == "day":
            body = "Which day should we ask people about?"
            self.add_select(
                "Choose a day",
                "day",
                [
                    discord.SelectOption(label=label, value=day.isoformat())
                    for day, label in day_choices(draft.input_timezone, self.now())
                ],
            )
        elif self.step == "start":
            body = "What’s the earliest time people could attend?"
            choices = starting_choices(draft.day, draft.input_timezone, self.now())
            zone = pytz.timezone(draft.input_timezone)
            by_half = {
                half: [
                    value
                    for value in choices
                    if (value.astimezone(zone).hour < 12) == (half == "am")
                ]
                for half in ("am", "pm")
            }
            if not by_half[self.half]:
                self.half = "am" if by_half["am"] else "pm"
            if by_half[self.half]:
                self.add_select(
                    "Choose beginning",
                    "start",
                    [
                        discord.SelectOption(
                            label=self.clock_label(value), value=str(int(value.timestamp()))
                        )
                        for value in by_half[self.half]
                    ],
                )
            else:
                body = "No times left on this day—please go back and choose another day."
            self.add_button("Morning (AM)", "am", row=1, disabled=not by_half["am"])
            self.add_button("Afternoon/evening (PM)", "pm", row=1, disabled=not by_half["pm"])
        elif self.step == "end":
            body = "What’s the latest time people could attend?"
            options = []
            for end in ending_choices(draft.start, draft.input_timezone):
                local = end.astimezone(pytz.timezone(draft.input_timezone))
                label = self.clock_label(end)
                if local.date() != draft.day:
                    label = f"Midnight · {local.strftime('%a, %b %d')} (next day)"
                minutes = int((end - draft.start).total_seconds() // 60)
                if minutes == 30:
                    length = "30-minute"
                elif minutes % 60:
                    length = f"{minutes // 60}½-hour"
                else:
                    length = f"{minutes // 60}-hour"
                options.append(
                    discord.SelectOption(
                        label=f"{label} · {length} window", value=str(int(end.timestamp()))
                    )
                )
            self.add_select("Choose ending", "end", options)
        else:
            body = (
                f"**{draft.day.strftime('%A, %B %d, %Y')}**\n"
                f"**{self.clock_label(draft.start)} – {self.clock_label(draft.end)} · {zone_label}**\n"
            )
            if draft.end.astimezone(pytz.timezone(draft.input_timezone)).date() != draft.day:
                body += "Ends at midnight at the beginning of the following day.\n"
            body += f"{len(build_blocks(draft.start, draft.end))} half-hour availability blocks\n"
            body += f"Your Discord local equivalent: {time_range(draft.start, draft.end)}\n"
            if draft.event_type:
                body += f"Type: {discord.utils.escape_markdown(draft.event_type)}\n"
            if draft.minimum_people is not None:
                body += f"Minimum people: {draft.minimum_people}\n"
            if draft.maximum_people is not None:
                body += f"Preferred maximum: {draft.maximum_people}\n"
            if draft.details:
                body += f"Details: {discord.utils.escape_markdown(draft.details)}\n"
            self.add_button("Post poll", "post", row=1, primary=True)
            self.add_button("Change times", "change", row=1)
        body += "\n\nPeople will react to the blocks they can attend. You’ll choose the actual event time after people respond."
        if self.step in ("start", "end"):
            body += "\nTimes skipped or repeated by daylight saving are unavailable."
        if self.step != "timezone":
            self.add_button("Back", "back", row=2)
        self.add_button("Discard", "discard", row=2)
        self.content = header + (f"\n{notice}\n\n" if notice else "\n") + body
        return self.content

    async def on_timeout(self):
        self.finished = True
        self.stop()
        if self.message:
            try:
                await self.message.edit(
                    content="This draft expired. Use `/plan create` to start again.",
                    embed=None,
                    view=None,
                )
            except discord.HTTPException:
                logger.info("Could not update expired planning draft %s", self.message.id)

    async def handle(self, interaction, action: str, value: str = "", *, revision=None):
        async with self.lock:
            if interaction.user.id != self.draft.leader_id:
                await interaction.response.send_message(
                    "This draft belongs to its creator.", ephemeral=True
                )
                return
            if not await self.cog._require_planning_channel(interaction):
                return
            if self.finished or self.now() - self.last_activity >= timedelta(minutes=15):
                await interaction.response.send_message(
                    "This draft is closed or expired. Use `/plan create` to start again.",
                    ephemeral=True,
                )
                return
            if revision is not None and revision != self.revision:
                await interaction.response.send_message(
                    "The choices changed. Please use the latest menus.", ephemeral=True
                )
                return
            self.last_activity = self.now()
            if action == "discard":
                self.finished = True
                self.stop()
                await interaction.response.edit_message(
                    content="Draft discarded. No poll was posted.", embed=None, view=None
                )
                return
            if action == "post" and self.step == "preview":
                try:
                    self.draft.validate_times(self.now())
                except ValueError as exc:
                    self.draft.day = self.draft.start = self.draft.end = None
                    self.step = "day"
                    await interaction.response.edit_message(
                        embed=discord.Embed(description=self.render(str(exc))), view=self
                    )
                    return
                # One posting attempt per draft, including uncertain HTTP outcomes.
                self.finished = True
                self.stop()
                await interaction.response.defer()
                await self.cog.post_draft(interaction, self.draft)
                return
            try:
                self.advance(action, value)
                notice = ""
            except ValueError as exc:
                notice = str(exc)
            await interaction.response.edit_message(
                embed=discord.Embed(description=self.render(notice)), view=self
            )

    def advance(self, action: str, value: str):
        draft = self.draft
        if action == "zone" and self.step == "timezone" and value in TIMEZONES:
            draft.input_timezone = value
            draft.day = draft.start = draft.end = None
        elif action == "continue" and self.step == "timezone":
            self.step = "day"
        elif action == "day" and self.step == "day":
            day = date.fromisoformat(value)
            if day not in {d for d, _ in day_choices(draft.input_timezone, self.now())}:
                raise ValueError("Please select a day from the refreshed list.")
            draft.day, draft.start, draft.end = day, None, None
            if not starting_choices(day, draft.input_timezone, self.now()):
                raise ValueError("No times left on this day—please choose another day.")
            self.half, self.step = "pm", "start"
        elif action in ("am", "pm") and self.step == "start":
            self.half = action
        elif action == "start" and self.step == "start":
            start = datetime.fromtimestamp(int(value), timezone.utc)
            if start not in starting_choices(draft.day, draft.input_timezone, self.now()):
                raise ValueError("That beginning is no longer available. Choose another time.")
            draft.start, draft.end = start, None
            self.step = "end"
        elif action == "end" and self.step == "end":
            end = datetime.fromtimestamp(int(value), timezone.utc)
            if end not in ending_choices(draft.start, draft.input_timezone):
                raise ValueError("Please choose an ending from the list.")
            draft.end = end
            self.step = "preview"
        elif action == "change":
            draft.day = draft.start = draft.end = None
            self.step = "timezone"
        elif action == "back" and self.step != "timezone":
            self.step = STEPS[STEPS.index(self.step) - 1]
            if self.step in ("timezone", "day"):
                draft.day = draft.start = draft.end = None
            elif self.step == "start":
                draft.start = draft.end = None
            elif self.step == "end":
                draft.end = None
        else:
            raise ValueError("Please use the current choices.")

    async def on_error(self, interaction, error, item):
        logger.error("Planning wizard failed", exc_info=(type(error), error, error.__traceback__))
        message = "The picker could not complete that step. Please start again with `/plan create`."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

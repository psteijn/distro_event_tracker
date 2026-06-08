from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from distro_event_tracker.events.cog import EventCog


class MockResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, *, embed=None, ephemeral=False):
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})


class MockInteraction:
    def __init__(self):
        self.id = 123
        self.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.user = SimpleNamespace(id=456, mention="@Tester")
        self.channel_id = 789
        self.channel = SimpleNamespace(id=self.channel_id)
        self.response = MockResponse()
        self.created_message = SimpleNamespace(id=999)

    async def original_response(self):
        return self.created_message


class MockRuntime:
    def __init__(self):
        self.calls = []

    def __getattr__(self, command_name):
        async def command(ctx, **kwargs):
            self.calls.append((command_name, ctx, kwargs))

        return command


async def invoke_distro(cog, interaction, event_type, name):
    await cog.distro.callback(cog, interaction, event_type, name)


def test_distro_requires_valid_type_and_name_options():
    parameters = {parameter.name: parameter for parameter in EventCog.distro.parameters}

    assert parameters["type"].required is True
    assert [(choice.name, choice.value) for choice in parameters["type"].choices] == [
        ("Dungeon (1x)", "dungeon"),
        ("Miniboss (1x)", "miniboss"),
        ("Boss (2x)", "boss"),
        ("T8 (1x)", "t8"),
        ("Omniboss (8x)", "omniboss"),
    ]
    assert parameters["name"].required is True
    assert parameters["name"].min_value == 1
    assert parameters["name"].max_value == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "command_name", "name_parameter"),
    [
        ("dungeon", "dungeon", "dungeon_name"),
        ("miniboss", "miniboss", "miniboss_name"),
        ("boss", "boss", "boss_name"),
        ("t8", "t8", "t8_name"),
        ("omniboss", "omniboss", "omniboss_name"),
    ],
)
async def test_distro_dispatches_valid_event_types(event_type, command_name, name_parameter):
    runtime = MockRuntime()
    cog = EventCog(runtime)
    interaction = MockInteraction()

    await invoke_distro(cog, interaction, event_type, "  Event Name  ")

    called_command, ctx, kwargs = runtime.calls[0]
    assert called_command == command_name
    assert kwargs == {name_parameter: "Event Name"}
    assert ctx.author is interaction.user
    assert ctx.channel is interaction.channel
    assert ctx.message.id == interaction.id
    assert ctx.message.created_at == interaction.created_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "name"),
    [
        ("", "Event Name"),
        ("unknown", "Event Name"),
        ("boss", ""),
        ("boss", "   "),
        ("boss", "x" * 201),
    ],
)
async def test_distro_rejects_invalid_values_without_creating_event(event_type, name):
    runtime = MockRuntime()
    cog = EventCog(runtime)
    interaction = MockInteraction()

    await invoke_distro(cog, interaction, event_type, name)

    assert runtime.calls == []
    assert interaction.response.messages == [
        {
            "content": (
                "Please provide both a valid event type and an event name between 1 and 200 "
                "characters."
            ),
            "embed": None,
            "ephemeral": True,
        }
    ]


@pytest.mark.asyncio
async def test_distro_context_sends_public_event_and_returns_created_message():
    runtime = MockRuntime()

    async def boss(ctx, **kwargs):
        message = await ctx.send(embed="event embed")
        runtime.calls.append(("boss", message, kwargs))

    runtime.boss = boss
    cog = EventCog(runtime)
    interaction = MockInteraction()

    await invoke_distro(cog, interaction, "boss", "Event Name")

    assert interaction.response.messages == [
        {"content": None, "embed": "event embed", "ephemeral": False}
    ]
    assert runtime.calls == [("boss", interaction.created_message, {"boss_name": "Event Name"})]


@pytest.mark.asyncio
async def test_distro_rejects_wrong_channel_without_creating_event():
    runtime = MockRuntime()
    cog = EventCog(runtime, "ocean", "123456")
    interaction = MockInteraction()

    await invoke_distro(cog, interaction, "boss", "Event Name")

    assert runtime.calls == []
    assert interaction.response.messages == [
        {
            "content": "`/ocean` can only be used in the designated event channel.",
            "embed": None,
            "ephemeral": True,
        }
    ]

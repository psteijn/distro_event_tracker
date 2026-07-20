import asyncio

import pytest

from distro_event_tracker.health import HealthServer


class FakeBot:
    def __init__(self, *, ready=False, closed=False):
        self.ready = ready
        self.closed = closed

    def is_ready(self):
        return self.ready

    def is_closed(self):
        return self.closed


async def request(server: HealthServer, path: str) -> tuple[int, str]:
    socket = server.server.sockets[0]
    host, port = socket.getsockname()[:2]
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = (await reader.read()).decode()
    writer.close()
    await writer.wait_closed()
    status = int(response.split()[1])
    return status, response


@pytest.mark.asyncio
async def test_health_endpoints_track_discord_readiness():
    bot = FakeBot()
    server = HealthServer(bot, host="127.0.0.1", port=0)
    await server.start()
    try:
        assert (await request(server, "/health/live"))[0] == 200
        assert (await request(server, "/health/ready"))[0] == 503

        bot.ready = True
        assert (await request(server, "/health/ready"))[0] == 200

        bot.closed = True
        assert (await request(server, "/health/ready"))[0] == 503
        assert (await request(server, "/unknown"))[0] == 404
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_health_endpoint_can_use_explicit_gateway_readiness():
    bot = FakeBot()
    connected = False
    server = HealthServer(
        bot,
        host="127.0.0.1",
        port=0,
        readiness_check=lambda: connected,
    )
    await server.start()
    try:
        assert (await request(server, "/health/ready"))[0] == 503
        connected = True
        assert (await request(server, "/health/ready"))[0] == 200
    finally:
        await server.close()

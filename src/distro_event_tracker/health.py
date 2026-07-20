"""Small dependency-free HTTP health server for container probes."""

import asyncio
from collections.abc import Callable
from typing import Protocol


class BotHealth(Protocol):
    def is_ready(self) -> bool: ...

    def is_closed(self) -> bool: ...


class HealthServer:
    """Expose process liveness and Discord readiness on an internal HTTP port."""

    def __init__(
        self,
        bot: BotHealth,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        server_factory: Callable = asyncio.start_server,
        readiness_check: Callable[[], bool] | None = None,
    ) -> None:
        self.bot = bot
        self.host = host
        self.port = port
        self.server_factory = server_factory
        self.readiness_check = readiness_check or (
            lambda: self.bot.is_ready() and not self.bot.is_closed()
        )
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.server = await self.server_factory(self._handle_request, self.host, self.port)

    async def close(self) -> None:
        if self.server is None:
            return
        self.server.close()
        await self.server.wait_closed()
        self.server = None

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=2)
            parts = request_line.decode("ascii", errors="replace").split()
            path = parts[1] if len(parts) >= 2 else ""

            if path == "/health/live":
                status, body = 200, b"live\n"
            elif path == "/health/ready" and self.readiness_check():
                status, body = 200, b"ready\n"
            elif path == "/health/ready":
                status, body = 503, b"not ready\n"
            else:
                status, body = 404, b"not found\n"

            reason = {200: "OK", 404: "Not Found", 503: "Service Unavailable"}[status]
            writer.write(
                f"HTTP/1.1 {status} {reason}\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n\r\n".encode("ascii") + body
            )
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

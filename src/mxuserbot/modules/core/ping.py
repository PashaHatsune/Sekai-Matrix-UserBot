import time

from ...core import loader, utils

from mautrix.types import MessageEvent, EventType
from mautrix.client import Client


class Meta:
    name = "PingPong"
    _cls_doc = "Simple ping-pong + dm checker"
    version = "1.1.0"
    tags = ["system"]


@loader.tds
class PingPongModule(loader.Module):
    """Ping-pong module"""

    strings = {
        "name": "PingPong",
        "pinging": "<b>🏓 Pinging...</b>",
        "pong": "<b>🏓 Pong!</b>\n<b>🚀 Latency:</b> <code>{} ms</code>",
        "dm_yes": "<b>📩 Это личка (DM)</b>",
        "dm_no": "<b>👥 Это не личка, а группа/комната</b>",
    }

    @loader.command()
    async def ping(self, mx, event):
        """Check bot latency"""
        start = time.perf_counter()

        message = await utils.answer(mx, self.strings("pinging"))

        end = time.perf_counter()
        duration = round((end - start) * 1000, 2)

        await utils.answer(
            message,
            self.strings("pong").format(duration)
        )
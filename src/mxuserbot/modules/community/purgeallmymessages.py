import asyncio
from mautrix.client import Client
from ...core import loader


@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "PurgeAllMe",
        "done": "Готово. Удалено {count} сообщений.",
        "_cls_doc": "1",
        "error": "Ошибка при обработке истории чата.",
    }

    @loader.command()
    async def purgeallme(self, mx: Client, event):
        """1"""
        room_id = event.room_id
        my_id = mx.client.mxid

        self.logger.info(f"[PURGE] start room={room_id}")

        candidates = set()
        token = None
        page = 0

        while True:
            page += 1

            resp = await mx.client.api.request(
                "GET",
                f"/_matrix/client/v3/rooms/{room_id}/messages",
                query_params={
                    "dir": "b",
                    "limit": "100",
                    "from": token or "",
                },
            )

            events = resp.get("chunk", [])
            token = resp.get("end")

            if not events:
                self.logger.info("[PURGE] stop: empty chunk")
                break

            self.logger.info(f"[PURGE] page={page} events={len(events)}")

            for msg in events:
                try:
                    if msg.get("sender") != my_id:
                        continue

                    if msg.get("type") not in (
                        "m.room.message",
                        "m.room.encrypted",
                        "m.reaction",
                    ):
                        continue

                    event_id = msg.get("event_id")
                    if not event_id or event_id == event.event_id:
                        continue

                    candidates.add(event_id)

                except Exception as e:
                    self.logger.warning(f"[PURGE] skip: {e}")

            if not token:
                self.logger.info("[PURGE] no next token")
                break

            await asyncio.sleep(2)

        self.logger.info(f"[PURGE] collected={len(candidates)}")

        deleted = 0

        for eid in list(candidates):
            try:
                await mx.client.redact(
                    room_id=room_id,
                    event_id=eid,
                    reason="purge all messages",
                )

                deleted += 1
                self.logger.info(f"[PURGE] deleted {eid} ({deleted})")

                await asyncio.sleep(2)

            except Exception as e:
                self.logger.warning(f"[PURGE] fail {eid}: {e}")

        self.logger.info(f"[PURGE] done={deleted}")

        await mx.answer(self.strings["done"].format(count=deleted))
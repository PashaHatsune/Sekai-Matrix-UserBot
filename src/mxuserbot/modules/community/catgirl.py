import aiohttp
from mautrix.types import (
    MessageEvent, ImageInfo, 
)
from ...core import loader
from mautrix.client import Client

@loader.tds
class MatrixModule(loader.Module):
    strings = {"name": "CatGirlModule", "error": "Ошибка API", "_cls_doc": "1"}

    @loader.command()
    async def catgirl(self, mx: Client, event: MessageEvent):
        """Отправляет фото кошко-девочки (E2EE Ready)."""
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.nekosia.cat/api/v1/images/catgirl") as r:
                if r.status != 200: 
                    return await mx.send_text(event.room_id, self.strings["error"])
                data = await r.json()
                url = data["image"]["original"]["url"]
                filename = url.split("/")[-1] or "catgirl.png"
            
            async with s.get(url) as img:
                image_bytes = await img.read()


        await mx.client.send_image(
            room_id=event.room_id,
            file_bytes=image_bytes,
            info=ImageInfo(
                mimetype="image/png",
                size=len(image_bytes)
            ),
            file_name="catgirl.png",
            caption="Моя кошко-девочка"
        )
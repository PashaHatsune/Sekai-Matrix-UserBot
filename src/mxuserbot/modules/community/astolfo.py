import aiohttp
from mautrix.types import MessageEvent
from ...core import loader

@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "AstolfoModule",
        "_cls_doc": "Скидывает случайные изображения Астольфо с astolfo.rocks",
        "error_api": "Api astolfo.rocks недоступно",
        "error_image": "Не удалось скачать или загрузить изображение",
        "invalid_rating": "Неверный рейтинг. Доступные: safe, questionable, explicit"
    }

    @loader.command()
    async def astolfo(self, mx, event: MessageEvent):
        """
        [rating] - Отправить фото Астольфо.
        Рейтинги: safe (по умолчанию), questionable, explicit
        """
        async with aiohttp.ClientSession() as s:
            params = {"rating": "safe"}
            # 1. Запрос к API за метаданными
            async with s.get("https://astolfo.rocks/api/images/random", params=params) as r:
                if r.status != 200:
                    return await mx.client.send_text(
                        room_id=event.room_id, 
                        html=self.strings["error_api"]
                    )
                
                data = await r.json()
                
                image_id = data["id"]
                ext = data["file_extension"]
                image_url = f"https://astolfo.rocks/astolfo/{image_id}.{ext}"
                
                filename = f"{image_id}.{ext}"
                mime = data.get("mimetype", "image/jpeg")

                async with s.get(image_url) as img:
                    if img.status != 200:
                        return await mx.client.send_text(
                            room_id=event.room_id, 
                            html=self.strings["error_image"]
                        )
                    image_bytes = await img.read()

                    mxc = await mx.client.upload_media(
                        data=image_bytes,
                        mime_type=mime,
                        filename=filename
                    )

            await mx.client.send_image(
                room_id=event.room_id,
                url=mxc,
                file_name=filename
            )
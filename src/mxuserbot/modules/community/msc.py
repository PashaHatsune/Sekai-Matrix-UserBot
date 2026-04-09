import aiohttp
from mautrix.types import MessageEvent
from mautrix.api import Method
from ...core import loader
from ...core import utils

@loader.tds
class MatrixModule(loader.Module):
    """Управление Rich Presence статусом (MSC4320)"""
    
    strings = {
        "name": "MSC4320-RPC",
        "_cls_doc" : "1",
        "success": "Статус успешно обновлен!",
        "error": "Ошибка: ```{}```",
        "stop": "Статус удален.",
        "usage_media": "Использование: ```.listening Артист | Трек | [Альбом] | [Ссылка] | [Плеер] | [URL Обложки]```>",
        "usage_play": "Использование: ```.playing Название | [Детали] | [URL Иконки]```",
        "usage_watch": "Использование: ```.watching Название | [Серия/Описание] | [URL Обложки]```",
    }

    RPC_NAMESPACE = "com.ip-logger.msc4320.rpc"

    async def _get_mxc_from_url(self, mx, url: str) -> str:
        """Скачивает файл и загружает в медиа-репозиторий Matrix для получения mxc://"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    raise Exception(f"Не удалось загрузить изображение (HTTP {resp.status})")
                data = await resp.read()
                mime = resp.headers.get("Content-Type", "image/png")
                return await mx.client.upload_media(data, mime_type=mime)

    async def _set_rpc_api(self, mx, rpc_data: dict):
        """Отправляет сформированные данные в профиль пользователя"""
        user_id = mx.client.mxid
        endpoint = f"_matrix/client/v3/profile/{user_id}/{self.RPC_NAMESPACE}"
        payload = {self.RPC_NAMESPACE: rpc_data}
        return await mx.client.api.request(Method.PUT, endpoint, content=payload)

    @loader.command()
    async def listening(self, mx, event: MessageEvent):
        """<артист> | <трек> | [альбом] | [ссылка] | [плеер] | [обложка]"""
        args = utils.get_args_raw(event.content.body)
        if not args:
            return await mx.client.send_text(event.room_id, self.strings["usage_media"], html=True)

        parts = [p.strip() for p in args.split("|")]
        if len(parts) < 2:
            return await mx.client.send_text(event.room_id, self.strings["usage_media"], html=True)

        try:
            mxc_cover = await self._get_mxc_from_url(mx, parts[5]) if len(parts) > 5 and parts[5].startswith("http") else None
            
            rpc_data = {
                "type": f"{self.RPC_NAMESPACE}.media",
                "artist": parts[0],
                "track": parts[1],
                "album": parts[2] if len(parts) > 2 and parts[2] else parts[0],
                "streaming_link": parts[3] if len(parts) > 3 and parts[3] else None,
                "player": parts[4] if len(parts) > 4 and parts[4] else "Matrix",
                "cover_art": mxc_cover
            }
            
            await self._set_rpc_api(mx, {k: v for k, v in rpc_data.items() if v is not None})
            await mx.client.send_text(event.room_id, self.strings["success"], html=True)
        except Exception as e:
            await mx.client.send_text(event.room_id, self.strings["error"].format(utils.escape_html(str(e))), html=True)

    @loader.command()
    async def playing(self, mx, event: MessageEvent):
        """<название> | [детали] | [URL иконки]"""
        args = utils.get_args_raw(event.content.body)
        if not args:
            return await mx.client.send_text(event.room_id, self.strings["usage_play"], html=True)

        parts = [p.strip() for p in args.split("|")]
        
        try:
            mxc_icon = await self._get_mxc_from_url(mx, parts[2]) if len(parts) > 2 and parts[2].startswith("http") else None
            
            rpc_data = {
                "type": f"{self.RPC_NAMESPACE}.activity",
                "name": parts[0],
                "details": parts[1] if len(parts) > 1 else None,
                "image": mxc_icon
            }

            await self._set_rpc_api(mx, {k: v for k, v in rpc_data.items() if v is not None})
            await mx.client.send_text(event.room_id, self.strings["success"], html=True)
        except Exception as e:
            await mx.client.send_text(event.room_id, self.strings["error"].format(utils.escape_html(str(e))), html=True)

    @loader.command()
    async def watching(self, mx, event: MessageEvent):
        """<название> | [описание] | [URL обложки]"""
        args = utils.get_args_raw(event.content.body)
        if not args:
            return await mx.client.send_text(event.room_id, self.strings["usage_watch"], html=True)

        parts = [p.strip() for p in args.split("|")]
        
        try:
            mxc_icon = await self._get_mxc_from_url(mx, parts[2]) if len(parts) > 2 and parts[2].startswith("http") else None
            
            rpc_data = {
                "type": f"{self.RPC_NAMESPACE}.activity",
                "name": parts[0],
                "details": f"📺 Смотрит: {parts[1]}" if len(parts) > 1 else "📺 Смотрит",
                "image": mxc_icon
            }

            await self._set_rpc_api(mx, {k: v for k, v in rpc_data.items() if v is not None})
            await mx.client.send_text(event.room_id, "<b>[RPC]</b> Статус просмотра установлен!", html=True)
        except Exception as e:
            await mx.client.send_text(event.room_id, self.strings["error"].format(utils.escape_html(str(e))), html=True)

    @loader.command()
    async def rpc_stop(self, mx, event: MessageEvent):
        """Удалить Rich Presence статус"""
        endpoint = f"_matrix/client/v3/profile/{mx.client.mxid}/{self.RPC_NAMESPACE}"

        await mx.client.api.request(Method.DELETE, endpoint)
        await mx.client.send_text(event.room_id, self.strings["stop"], html=True)

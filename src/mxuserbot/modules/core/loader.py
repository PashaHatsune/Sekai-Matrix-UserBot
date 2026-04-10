import aiohttp
from pathlib import Path
from ...core import loader, utils

@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "DLMod",
        "_cls_doc": "Скачивает и загружает модуль из удаленного репозитория",
        "no_url": "❌ URL не указан",
        "downloading": "⏳ Скачиваю модуль...",
        "done": "✅ Модуль загружен: <code>{name}</code>",
        "error": "❌ Ошибка: <code>{err}</code>"
    }

    @loader.command()
    async def mdl(self, mx, event):
        """!mdl <url> — скачивает и подгружает модуль"""
        text = getattr(event.content, "body", "")
        parts = text.split()
        
        if len(parts) < 2:
            return await utils.answer(mx, event.room_id, self.strings["no_url"])
        
        url = parts[1]
        await utils.answer(mx, event.room_id, self.strings["downloading"])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    code = await resp.text()

            filename = Path(url).name
            if not filename.endswith(".py"):
                filename += ".py"

            path = Path(self.loader.community_path) / filename
            path.write_text(code, encoding="utf-8")

            await self.loader.register_module(path, mx, is_core=False)

            await utils.answer(mx, event.room_id, self.strings["done"].format(name=filename))

        except Exception as e:
            await utils.answer(mx, event.room_id, self.strings["error"].format(err=str(e)))
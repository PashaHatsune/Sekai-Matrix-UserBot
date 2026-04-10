import aiohttp
from pathlib import Path
from ...core import loader, utils
import sys
from typing import Any
from mautrix.types import MessageEvent
from ...core import loader, utils


@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "DLMod",
        "_cls_doc": "Скачивает и загружает модуль из удаленного репозитория",
        "no_url": "❌ URL не указан",
        "downloading": "⏳ Скачиваю модуль...",
        "done": "✅ Модуль загружен: <code>{name}</code>",
        "error": "❌ Ошибка: <code>{err}</code>",
        "reloaded_header": "<b>♻️ Модули перезагружены:</b>\n",
        "module_item": "▫️ <code>{name}</code>\n",
        "no_name": "❌ Укажите имя модуля для выгрузки",
        "not_found": "❌ Модуль {name} не найден среди активных",
        "unloaded": "✅ Модуль {name} успешно выгружен и удалён",
        "error": "❌ Ошибка: {err}"
    }

    @loader.command()
    async def mdl(self, mx, event):
        """!mdl <url> — скачивает и подгружает модуль"""
        args = utils.get_args_raw(event.content.body)
        
        if not args:
            return await mx.answer(self.strings.get("no_url"))
        
        url = args.strip()
        await mx.answer(self.strings.get("downloading"))

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

            await mx.answer(self.strings.get("done").format(name=filename))

        except Exception as e:
            await mx.answer(self.strings.get("error").format(err=str(e)))

        
    @loader.command()
    async def reload(self, mx: Any, event: MessageEvent):
        """Перезагрузка всех модулей"""
        
        active_names = list(mx.active_modules.keys())

        for name in active_names:
            try:
                await self.loader.unload_module(name, mx)
            except Exception:
                continue

        await self.loader.register_all(mx)

        msg = self.strings.get("reloaded_header")
        for name in mx.active_modules.keys():
            msg += self.strings.get("module_item").format(name=name)

        await mx.answer(msg)

    
    @loader.command()
    async def unlmd(self, mx, event):
        """!unlmd <имя модуля> — выгружает и удаляет модуль"""
        text = getattr(event.content, "body", "")
        parts = text.split()
        if len(parts) < 2:
            return await mx.client.send_text(event.room_id, self.strings["no_name"])
        
        name = parts[1]

        if name not in mx.all_modules.active_modules:
            return await mx.client.send_text(event.room_id, self.strings["not_found"].format(name=name))
        
        try:
            await mx.all_modules.unload_module(name, mx)

            path = Path(mx.all_modules.community_path) / f"{name}.py"
            if path.exists():
                path.unlink()

            await mx.client.send_text(event.room_id, self.strings["unloaded"].format(name=name))

        except Exception as e:
            await mx.client.send_text(event.room_id, self.strings["error"].format(err=str(e)))
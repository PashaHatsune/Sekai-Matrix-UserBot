from mautrix.types import ImageInfo, MessageEvent
from ...core import loader, utils

class Meta:
    name = "HelperModule"
    _cls_doc = "Отображает список всех доступных команд и информацию о системе."
    version = "1.0.0"
    dependencies = ["patchlib"]
    tags = ["helper"]

@loader.tds
class HelperModule(loader.Module):
    strings = {
        "header": "<b>💠 {name}</b><br><i>{desc}</i><br><br>",
        "modules_title": "<b>Доступные модули и команды:</b><br>",
        "module_item": "▫️ <b>{name}</b> — <i>{desc}</i><br>    ⬥ {commands}<br><br>",
        "cmd_info": "<b>Команда:</b> <code>{prefix}{name}</code><br><b>Описание:</b> {desc}",
        "cmd_not_found": "❌ Команда <code>{prefix}{name}</code> не найдена.",
        "no_desc": "Описание отсутствует",
        "no_cmds": "Нет команд",
        "info_caption" : (
            "<b><u>MxUserBot Info</u></b><br>"
            "🆔 | Версия: <code>0.1</code><br>"
            "🌐 | Статус: <code>Alpha</code><br>"
            "👩‍💻 | Исходники: "
            "<a href='https://github.com/PashaHatsune/MxUserbot'>GitHub</a><br>"
        )
    }

    @loader.command()
    async def help(self, mx, event: MessageEvent):
        """Отображает список команд"""
        
        if self._is_core:
            await self._db.get("core", "prefix")

        parts = event.content.body.split()
        args = parts[1] if len(parts) > 1 else None
        prefix = await mx.get_prefix()

        if not args:
            msg = self.strings.get("header").format(
                name=self.Meta.name,
                desc=self.Meta._cls_doc
            )
            msg += self.strings.get("modules_title")

            for mod in mx.active_modules.values():
                if hasattr(mod, "commands") and mod.commands:
                    cmds = ", ".join([f"<code>{prefix}{c}</code>" for c in mod.commands.keys()])
                else:
                    cmds = self.strings.get("no_cmds")

                msg += self.strings.get("module_item").format(
                    name=mod.Meta.name,
                    desc=mod.Meta._cls_doc,
                    commands=cmds
                )

            return await mx.answer(msg)

        cmd_name = args.lower()
        for mod in mx.active_modules.values():
            if hasattr(mod, "commands") and cmd_name in mod.commands:
                func = mod.commands[cmd_name]
                doc = mod.strings.get(f"_cmd_doc_{cmd_name}") or func.__doc__ or self.strings.get("no_desc")

                res = self.strings.get("cmd_info").format(
                    prefix=prefix,
                    name=cmd_name,
                    desc=doc
                )
                return await mx.answer(res)

        await mx.answer(
            self.strings.get("cmd_not_found").format(
                prefix=prefix,
                name=cmd_name
            )
        )

    @loader.command()
    async def info(self, mx, event: MessageEvent):
        """Отправить карточку с информацией о боте"""
        
        await utils.send_image(
            mx=mx, 
            room_id=event.room_id,
            url="mxc://pashahatsune.pp.ua/ZPKENBwSwKgbFvrYWByGr1140eNqWQyL",
            caption=self.strings.get("info_caption"),
            file_name="info.png",
            info=ImageInfo(
                width=600,
                height=335,
                mimetype="image/png"
            )
        )
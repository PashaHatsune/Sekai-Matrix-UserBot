from ...core import loader


@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "PrefixModule",
        "_cls_doc": "Управление префиксом",
        "allowed_symbols": "!\"./\\,;:@#$%^&*-_+=?|~",
        "error_no_args": "<b>Ошибка:</b> вы не указали префикс.\nПример: <code>.set_prefix !</code>",
        "error_too_long": "<b>Ошибка:</b> префикс должен состоять только из <b>одного</b> символа.",
        "error_set_prefix": "<b>Ошибка:</b> символ <code>{new_prefix}</code> запрещен.\n"
                            "Можно использовать только: <code>{allowed_symbols}</code>",
        "success_set_prefix": "✅ Префикс успешно изменен на: <code>{new_prefix}</code>"
    }

    @loader.command()
    async def set_prefix(self, bot, event):
        """Установить новый префикс (только спец. символы)"""
        
        parts = event.body.split()
        
        if len(parts) < 2:
            await bot.send_text(
                event.room,
                self.strings["error_no_args"]
            )
            return

        new_prefix = parts[1]

        if len(new_prefix) != 1:
            await bot.send_text(
                event.room,
                self.strings["error_too_long"]
            )
            return

        if new_prefix not in self.strings["allowed_symbols"]:
            await bot.send_text(
                event.room,
                self.strings["error_set_prefix"].format(
                    new_prefix=new_prefix,
                    allowed_symbols=self.strings["allowed_symbols"]
                )
            )
            return

        query = [new_prefix]
        await self._set("prefix", query)
        bot.prefixes = query

        await bot.send_text(
            event.room,
            self.strings["success_set_prefix"].format(new_prefix=new_prefix)
        )
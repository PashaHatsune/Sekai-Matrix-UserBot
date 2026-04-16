from typing import Any
from mautrix.types import MessageEvent
from ...core import loader, utils

class Meta:
    name = "PrefixModule"
    _cls_doc = "Управление префиксом команд юзербота."
    version = "1.0.1"
    tags = ["settings"]


@loader.tds
class PrefixModule(loader.Module):
    config = {
        "allowed_symbols": loader.ConfigValue(default="!\"./\\,;:@#$%^&*-_+=?|~", description="list allowed symbols"),
    }

    strings = {
        "error_no_args": "❌ | <b>No prefix specified.</b><br>Example: <code>.set_prefix !</code>",
        "error_too_long": "❌ | <b>The prefix must be exactly <u>one</u></b> character long.",
        "error_set_prefix": "❌ | <b>The character <code>{new_prefix}</code> is not allowed.</b><br>"
                            "You can only use: <code>{allowed_symbols}</code>",
        "success_set_prefix": "✅ | <b>Prefix successfully changed to</b>: <code>{new_prefix}</code>"
    }

    @loader.command()
    async def set_prefix(self, mx, event: MessageEvent):
        """Установить новый префикс (только спец. символы)"""

        args = await utils.get_args(
            mx=mx,
            event=event
        )
    
        if len(args) < 1:
            return await utils.answer(mx, self.strings.get("error_no_args"))

        new_prefix = args[0]

        if len(new_prefix) != 1:
            return await utils.answer(mx, self.strings.get("error_too_long"))

        allowed = self.config.get("allowed_symbols")

        if new_prefix not in allowed:
            return await utils.answer(mx, 
                self.strings.get("error_set_prefix").format(
                    new_prefix=new_prefix,
                    allowed_symbols=allowed
                )
            )

        query = [new_prefix]
        await self._db.set("core", "prefix", query)
        
        if hasattr(mx, "prefixes"):
            mx.prefixes = [query]

        await utils.answer(mx, 
            self.strings.get("success_set_prefix").format(new_prefix=new_prefix)
        )
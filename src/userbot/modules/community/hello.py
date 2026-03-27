from ...core import loader


@loader.tds
class MatrixModule(loader.Module):
    strings = {
        "name": "HelloModule",
        "_cls_doc": "выводит приветственное сообщение",
        "soo": "приветствие"
    }

    @loader.command()
    async def hello(self, bot, event):
        """Отправляет приветственное сообщение"""
        await bot.send_text(event.room, self.strings["soo"])

        # await bot.send_image(room, "mxc://pashahatsune.duckdns.org/YyQjXCmBkpHvkkBTZxMdsIgw", event.body)


        # await bot.send_image(room, "/home/miku/remote/dev/synapse/test.jpg", event.body)
        # await bot.send_video(room, "/home/miku/Documents/12.mp4", event.body)


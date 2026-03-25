
---

# Sekai-Matrix-UserBot

Matrix-юзербот, созданный как модульное переосмысление проекта [Hemppa](https://github.com/vranki/hemppa).

> **В РАЗРАБОТКЕ**
> Проект находится в ранней стадии. Опыта в коде пока мало, поэтому активно использовался ИИ. Не судите строго, я только учусь.

## Участие в разработке
Issue и Pull requests принимаются. Если есть идеи или код — присылайте, всё выслушаю и рассмотрю.

## О чем этот форк
После перехода из Telegram мне не хватало привычных юзерботов. Нашел Hemppa, но реализация «всё в одном файле» показалась неудобной. Решил форкнуть и переделать под нормальную структуру.

**Что изменено:**
*  +- нормальная система модулей
* проект разбит на core / modules
* Запуск через модуль
* поддержка uv
* доработаны методы 

## Установка

```bash
git clone https://github.com/PashaHatsune/Sekai-Matrix-UserBot.git
cd Sekai-Matrix-UserBot

# Синхронизация и запуск
uv sync
uv run -m src.userbot
```

## Как написать свой модуль

1.  Создай файл в папке модулей.
2.  Импортируй лоадер: `from ..core import loader`.
3.  Наследуй класс `MatrixModule` от `loader.Module`.

### Пример кода:

```python
from ..core import loader

@loader.tds
class MatrixModule(loader.Module):
    # Обязательные ключи: name [имя модуля] и _cls_doc [описание модуля]
    strings = {
        "name": "HelloModule",
        "_cls_doc": "выводит приветственное сообщение",
        "helloy": "Привет всем! Это тестовый модуль!"
    }

    @loader.command()
    # В функцию передаем: self, bot, room, event, args
    async def hello(self, bot, room, event, args):
        """Отправляет приветственное сообщение"""
        # По умолчанию команда будет !hello
        await bot.send_text(room, self.strings["helloy"])
```

> **Подсказка:** Чтобы задать свою команду, используй `@loader.command(name="mycommand")`. Тогда вызов будет через `!mycommand`.


---

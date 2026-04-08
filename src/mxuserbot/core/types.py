import asyncio
import contextlib
import logging
import sys
from abc import ABC
from typing import Any, AsyncGenerator, Optional, Dict, List

from loguru import logger
from ruamel.yaml.comments import CommentedMap

from mautrix.client import Client
from mautrix.client.state_store import MemoryStateStore as BaseMemoryStateStore
from mautrix.crypto.store import MemoryCryptoStore as BaseMemoryCryptoStore
from mautrix.types import (
    CrossSigningUsage,
    EventType,
    ImageInfo,
    MediaMessageEventContent,
    TOFUSigningKey,
)
from mautrix.util import markdown
from mautrix.util.config import BaseFileConfig, RecursiveDict, ConfigUpdateHelper

from ...settings import config
from . import utils

class ModuleConfig:
    def __init__(self, db, module_name, **defaults):
        self._db = db
        self._module_name = module_name
        self._cache = defaults.copy()

    async def _load_from_db(self):
        for key in self._cache.keys():
            val = await self._db.get(self._module_name, key, self._cache[key])
            self._cache[key] = val

    def __getitem__(self, key):
        return self._cache.get(key)

    def __setitem__(self, key, value):
        self._cache[key] = value
        asyncio.create_task(self._db.set(self._module_name, key, value))


class Module(ABC):
    __origin__ = "<unknown>"
    __module_hash__ = "unknown"
    __source__ = ""

    config = {}
    strings = {}

    async def _internal_init(self, name, db, allmodules):
        self.name = name
        self.db = db
        self.allmodules = allmodules
        self.enabled = True
        self.logger = logger.bind(name=self.name)
        
        self.strings = getattr(self.__class__, "strings", {}).copy()

        self.friendly_name = self.strings.get("name") or self.config.get("name") or self.__class__.__name__

        defaults = getattr(self, "config", {})
        self.config = ModuleConfig(self.db, self.name, **defaults)
        await self.config._load_from_db()

        self._commands = {}
        for cmd_name, func in utils.get_commands(self.__class__).items():
            self._commands[cmd_name] = getattr(self, func.__name__)
    
    def _help(self):
        """Возвращает основную документацию модуля"""
        return self.strings.get("_cls_doc", "Описание отсутствует")

    @property
    def commands(self):
        return self._commands

    async def _get(self, key, default=None): 
        return await self.db.get(self.name, key, default)
        
    async def _set(self, key, value): 
        return await self.db.set(self.name, key, value)

    async def _matrix_start(self, mx): pass
    async def _matrix_message(self, mx, event): pass
    async def _matrix_member(self, mx, event): pass




    def _matrix_stop(self, mx): pass
    async def _matrix_poll(self, mx, pollcount): pass
    


import aiohttp
from mautrix.crypto.attachments import encrypt_attachment


class UserBotClient(Client):
    async def send_image(
        self,
        room_id,
        url: str | None = None,
        file_bytes: bytes | None = None,
        info: ImageInfo | None = None,
        file_name: str | None = None,
        caption: str | None = None,
        relates_to=None,
        **kwargs,
    ):
        """Авто-шифрование для E2EE чатов с поддержкой caption"""
        if not url and not file_bytes:
            raise ValueError("Нужно указать либо url, либо file_bytes")

        file_name = file_name or "file.png"
        is_enc = await self.state_store.is_encrypted(room_id)

        if is_enc:
            if not file_bytes and url:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url) as r:
                        file_bytes = await r.read()

            enc_data, enc_info = encrypt_attachment(file_bytes)
            mxc = await self.upload_media(enc_data, mime_type="application/octet-stream", filename=file_name)
            enc_info.url = mxc

            content = MediaMessageEventContent(
                msgtype="m.image",
                body=caption or file_name,
                info=info,
                file=enc_info,
                relates_to=relates_to,
                format="org.matrix.custom.html",
                formatted_body=markdown.render(caption or file_name),
            )
        else:
            mxc_url = url or await self.upload_media(file_bytes, mime_type="image/png", filename=file_name)
            content = MediaMessageEventContent(
                msgtype="m.image",
                body=caption or file_name,
                info=info,
                url=mxc_url,
                filename=file_name,
                relates_to=relates_to,
                format="org.matrix.custom.html",
                formatted_body=markdown.render(caption or file_name),
            )

        return await self.send_message_event(
            room_id,
            EventType.ROOM_MESSAGE,
            content,
            **kwargs,
        )



class Config(BaseFileConfig):
    """Логика конфигурации через SQLite."""
    def __init__(self, path: str, base_path: str, db: Any = None) -> None:
        super().__init__(path, base_path)
        self.db = db
        self.owner = "core"
        self._default_values = {
            "matrix": {
                "base_url": config.matrix_config.base_url,
                "username": config.matrix_config.owner,
                "password": config.matrix_config.password.get_secret_value(),
                "device_id": "MXBT-SQL", # НОВЫЙ ID для чистой базы
                "log_room_id": "",
                "owner": config.matrix_config.owner
            },
            "logging": {"version": 1}
        }
        self._data = RecursiveDict(self._default_values, CommentedMap)

    def load_base(self) -> RecursiveDict:
        return RecursiveDict(self._default_values, CommentedMap)

    def load(self) -> None: pass
    def save(self) -> None: pass

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("matrix")
        helper.copy("logging")

    async def load_from_db(self) -> None:
        if not self.db: return
        async def fetch_recursive(data_dict: dict, prefix=""):
            for key, value in data_dict.items():
                full_key = f"{prefix}{key}"
                if isinstance(value, dict):
                    await fetch_recursive(value, f"{full_key}.")
                else:
                    db_value = await self.db.get(self.owner, full_key)
                    if db_value is not None:
                        self[full_key] = db_value
        await fetch_recursive(self._default_values)

    async def update_db_key(self, key: str, value: Any) -> None:
        self[key] = value
        if self.db:
            await self.db.set(self.owner, key, value)






class InterceptHandler(logging.Handler):
    """Перехватчик стандартных логов Python и перенаправление их в Loguru."""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
            
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
            
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())



class MemoryCryptoStore(BaseMemoryCryptoStore):
    """Исправленное хранилище ключей."""
    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        yield

    async def put_cross_signing_key(self, user_id: str, usage: CrossSigningUsage, key: str) -> None:
        """Фикс ошибки AttributeError: can't set attribute."""
        try:
            current = self._cross_signing_keys[user_id][usage]
            self._cross_signing_keys[user_id][usage] = TOFUSigningKey(key=key, first=current.first)
        except KeyError:
            self._cross_signing_keys.setdefault(user_id, {})[usage] = TOFUSigningKey(key=key, first=key)

class CustomMemoryStateStore(BaseMemoryStateStore):
    async def find_shared_rooms(self, user_id: str) -> list[str]:
        shared = []
        for room_id, members in getattr(self, "members", {}).items():
            if user_id in members: shared.append(room_id)
        return shared


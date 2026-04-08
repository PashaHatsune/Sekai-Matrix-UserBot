import os
import sys
import time
import logging
from typing import AsyncGenerator, Optional, Dict, List, Any

from loguru import logger
from mautrix.client import Client
from mautrix.api import HTTPAPI
from mautrix.types import MessageEvent, EventType, StateEvent, RoomDirectoryVisibility, ImageInfo, MediaMessageEventContent
from mautrix.util.program import Program
from mautrix.util.async_db import Database as MautrixDatabase
from mautrix.crypto.store.asyncpg import PgCryptoStore
from mautrix.crypto.store.asyncpg import PgCryptoStateStore 
from mautrix.api import Method
from mautrix.types import TrustState



from mautrix.crypto import OlmMachine


from .core.types import InterceptHandler
from .core.types import UserBotClient
from .core.types import Config
from .core.callback import CallBack
from .core.loader import Loader
from .core.security import SekaiSecurity 
from ..database import Database, AsyncSessionWrapper  








class MXUserBot(Program):
    """Главный класс юзербота."""
    
    def __init__(self) -> None:
        super().__init__(
            module='main',
            name='sekai-user-bot',
            description="Sekai Userbot",
            command="-",
            version="1.0.0",
            config_class=Config
        )
        self.client: Optional[Client] = None
        self.db: Optional[Database] = None
        self.all_modules: Optional[Loader] = None
        self.security: Optional[SekaiSecurity] = None
        
        self.active_modules: Dict[str, Any] = {}
        self.module_aliases: Dict[str, str] = {}  
        self.uri_cache: Dict[str, Any] = {}
        
        self.start_time: Optional[int] = None
        self.join_time: Optional[int] = None
        self.prefixes: List[str] = ["!", "."]


    async def _setup_log_room(self) -> str:
        """Проверяет конфиг на наличие комнаты логов, создает её при необходимости."""
        log_room_id = self.config["matrix"]["log_room_id"]

        if log_room_id:
            return log_room_id

        self.log.info("Комната логов не найдена в конфиге. Создаю новую...")
        owner_id = self.config["matrix"]["owner"]
        avatar_url = "mxc://pashahatsune.pp.ua/hGaNZRrDKOF5HlHjZ8VilRWj5QHFOXoy"

        initial_state = [
            {
                "type": "m.room.avatar",
                "state_key": "",
                "content": {"url": avatar_url}
            }
        ]

        new_room_id = await self.client.create_room(
            name="[LOGS] | MX-USERBOT",
            topic="Техническая комната для системных уведомлений и логов",
            is_direct=True,
            visibility=RoomDirectoryVisibility.PRIVATE,
            invitees=[owner_id],
            initial_state=initial_state
        )
        await self.client.join_room(new_room_id)
        await self.client.set_room_tag(new_room_id, "m.favourite", {"order": 0.0})
        await self.config.update_db_key("matrix.log_room_id", str(new_room_id))


        await self.client.send_text(new_room_id, "✅ Комната логов успешно инициализирована.")


        self.config["matrix"]["log_room_id"] = str(new_room_id)
        self.config.save()
        
        self.log.info(f"Создана комната для логов: {new_room_id}. ID сохранен в config.yaml")
        return str(new_room_id)


    async def log_to_room(self, message: str):
        """Отправляет текстовое сообщение в комнату логов."""
        target_room = self.config["matrix"]["log_room_id"]
        try:
            await self.client.send_image(
                target_room,
                url="mxc://pashahatsune.pp.ua/TYIaHOreKFTsWSG06xVzm5hA770Cm9K5",
                caption=message,
                file_name="photo.png",
            )
        except Exception as e:
                self.log.error(f"Ошибка отправки лога в комнату: {e}")


    def starts_with_command(
        self,
        body: str
    ) -> bool:
        """Проверяет, начинается ли сообщение с активного префикса."""
        return body.startswith(tuple(self.prefixes))


    def should_ignore_event(
        self,
        evt: MessageEvent
    ) -> bool:
        # if evt.sender == self.client.mxid:
        #     return True
        

        if evt.timestamp < (self.start_time - 10000):
            logger.debug(f"Игнорирую старое: {evt.timestamp} < {self.start_time}")
            return True

        if not evt.content.body:
            return True
            
        return False


    async def is_owner(
        self,
        evt: StateEvent
    ) -> bool:
        """Проверяет, является ли отправитель владельцем бота."""
        return evt.sender == self.config["owner"]

    def _setup_loguru(
        self
    ) -> None:
        """Настройка форматирования и обработчиков для Loguru."""
        logging.basicConfig(handlers=[InterceptHandler()], level="INFO", force=True)
        logger.remove()
        
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        logger.add(sys.stdout, format=log_format, colorize=True)



    def prepare_log(
        self
    ) -> None:
        """Инициализация логирования (переопределение базового метода)."""
        self._setup_loguru()
        self.log = logger.bind(name=self.name)


    def prepare(
        self
    ) -> None:
        """Подготовка бота к запуску."""
        super().prepare()
        self.add_startup_actions(self.setup_userbot())


    async def get_args(
        self, 
        body: str
    ) -> str:
        """Извлекает аргументы команды (текст после команды)."""
        for prefix in self.prefixes:
            if body.startswith(prefix):
                cmd_part = body[len(prefix):]
                parts = cmd_part.split(maxsplit=1)
                return parts[1] if len(parts) > 1 else ""
        return ""


    async def _load_prefixes(
        self
    ) -> None:
        """Загрузка префиксов из БД при старте."""
        db_result = await self.db.get("set_prefix", "prefix", None)

        if db_result:
            self.prefixes = db_result.value
            
        logger.info(f"Загружены префиксы: {self.prefixes}")


    async def _setup_security(
        self
    ) -> None:
        """Инициализация подсистемы безопасности."""
        self.security = SekaiSecurity(self)
        await self.security.init_security()


    async def _cleanup_empty_rooms(
        self
    ) -> None:
        """Вспомогательный метод: выход из пустых комнат при запуске."""
        joined_rooms = await self.client.get_joined_rooms()

        for room_id in joined_rooms:
            try:
                members = await self.client.get_joined_members(room_id)
                if len(members) == 1:
                    logger.info(f"В комнате {room_id} нет других пользователей. Покидаю...")
                    # await self.client.leave_room(room_id)
            except Exception as e:
                logger.error(f"Ошибка при очистке комнаты {room_id}: {e}")


    async def _register_handlers(
        self
    ) -> None:
        """Вспомогательный метод: регистрация обработчиков событий (Matrix)."""
        cb = CallBack(self)
        
        self.client.add_event_handler(
            EventType.ROOM_MEMBER, 
            self.security.gate(cb.invite_cb)
        )

        self.client.add_event_handler(
            EventType.ROOM_MEMBER, 
            cb.memberevent_cb  # Было self.security.gate(cb.memberevent_cb)
        )

        if hasattr(cb, "message_cb"):
            self.client.add_event_handler(
                EventType.ROOM_MESSAGE, 
                cb.message_cb  # Было self.security.gate(cb.message_cb)
            )


    async def setup_userbot(
        self
    ) -> None:
        try:
            session_wrapper = AsyncSessionWrapper() 
            self.db = Database(session_wrapper) 
            await self.db._sw.init_db()

            self.config.db = self.db
            await self.config.load_from_db()
            conf = self.config["matrix"]


            db_path = os.path.join(os.getcwd(), "crypto.db")
            self.log.info(f"Подключение к базе ключей E2EE: {db_path}")
            
            self.crypto_db = MautrixDatabase.create(f"sqlite:///{db_path}")
            await self.crypto_db.start() 

            self.log.info("Инициализация таблиц базы данных...")
            
            await PgCryptoStore.upgrade_table.upgrade(self.crypto_db)
            
            await PgCryptoStateStore.upgrade_table.upgrade(self.crypto_db)
            # ----------------------------------------------

            self.state_store = PgCryptoStateStore(self.crypto_db)
            self.crypto_store = PgCryptoStore(conf["username"], "sekai_secret_pickle_key", self.crypto_db)



            # 3. Инициализация Клиента
            self.client = UserBotClient(
                api=HTTPAPI(base_url=conf["base_url"]),
                state_store=self.state_store,
                sync_store=self.crypto_store
            )

            # 4. Логин
            self.log.info("Выполняю вход в Matrix...")
            await self.client.login(
                identifier=conf["username"],
                password=conf["password"],
                device_id=conf["device_id"]
            )
            self.log.info(f"Вход выполнен как {conf['device_id']}!")

            # 5. Настройка шифрования
            self.client.crypto = OlmMachine(self.client, self.crypto_store, self.state_store)
            self.client.crypto.allow_key_requests = True

            # Защита от краша при старых/битых сообщениях To-Device
            self.client.remove_event_handler(EventType.TO_DEVICE_ENCRYPTED, self.client.crypto.handle_to_device_event)
            async def safe_handle_to_device(evt):
                try:
                    await self.client.crypto.handle_to_device_event(evt)
                except Exception as e:
                    self.log.warning(f"Пропущено To-Device сообщение (битый ключ): {e}")
            self.client.add_event_handler(EventType.TO_DEVICE_ENCRYPTED, safe_handle_to_device)
            
            await self.client.crypto.load()
            if not await self.crypto_store.get_device_id():
                self.log.info("Публикация ключей устройства в Matrix...")
                await self.client.crypto.share_keys()

            # Доверие своим устройствам
            async def trust_own_devices():
                self.log.info("Синхронизация списка собственных устройств...")
                try:
                    resp = await self.client.api.request(Method.GET, "/_matrix/client/v3/devices")
                    my_devices = resp.get("devices",[])
                except Exception as e:
                    self.log.error(f"Не удалось получить список устройств: {e}")
                    return

                cached_devices = await self.crypto_store.get_devices(self.client.mxid) or {}
                updated_count = 0
                for dev in my_devices:
                    d_id = dev.get("device_id")
                    if not d_id or d_id == self.client.device_id: continue
                    
                    identity = await self.client.crypto.get_or_fetch_device(self.client.mxid, d_id)
                    if identity and identity.trust != TrustState.VERIFIED:
                        identity.trust = TrustState.VERIFIED
                        cached_devices[d_id] = identity
                        updated_count += 1
                        self.log.debug(f"Устройство {d_id} ({dev.get('display_name', 'Unknown')}) доверено.")

                if updated_count > 0:
                    await self.crypto_store.put_devices(self.client.mxid, cached_devices)
                    self.log.info(f"Успешно верифицировано новых устройств: {updated_count}")
                else:
                    self.log.info("Все устройства уже верифицированы.")

            await trust_own_devices()

            # 6. Инициализация модулей бота
            log_room = await self._setup_log_room()
            self.all_modules = Loader(self.db)
            await self.all_modules.register_all(self)
            self.active_modules = self.all_modules.active_modules

            await self._setup_security()
            await self._load_prefixes()
            await self._register_handlers()

            import datetime
            await self.log_to_room(f"🚀 **Sekai UserBot (SQLite Crypto)** запущен!\n"
                                f"Версия: `{self.version}`\n"
                                f"Время: `{datetime.datetime.now().strftime('%H:%M:%S')}`")
            
            await self._cleanup_empty_rooms()
            self.start_time = int(time.time() * 1000)

            self.log.info("Запуск синхронизации Matrix...")
            
            # ФИЛЬТР: Берем только новые сообщения, чтобы не было "красного спама" от истории
            sync_filter = {"room": {"timeline": {"limit": 1}}}
            await self.client.start(filter_data=sync_filter)
            
        except Exception as e:
            self.log.exception(f"Критическая ошибка при запуске бота: {e}")

import traceback
if __name__ == "__main__":
    try:
        bot = MXUserBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Работа бота завершена пользователем (Ctrl+C).")
    except Exception:
        traceback.print_exc(file=sys.stderr)
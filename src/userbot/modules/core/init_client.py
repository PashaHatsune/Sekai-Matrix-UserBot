from ....settings import config
import os
import sys
from nio import AsyncClient
from loguru import logger
import asyncio
# Импортируем реестр, чтобы обновить в нем переменные
from ... import registry 

# Глобальная переменная для хранения единственного экземпляра клиента
_client_instance = None

def init_client():
    global _client_instance
    
    # Если клиент уже был создан ранее, просто возвращаем его
    if _client_instance is not None:
        return _client_instance

    matrix_server = config.matrix_config.base_url
    bot_owner = config.matrix_config.owner
    access_token = config.matrix_config.access_token.get_secret_value()
    
    # Читаем настройки из окружения
    join_on_invite = os.getenv('JOIN_ON_INVITE', 'False').lower() == 'true'
    invite_whitelist = os.getenv('INVITE_WHITELIST', '').split(',')
    if invite_whitelist == ['']: invite_whitelist = []

    if matrix_server and bot_owner and access_token:
        logger.info(f"Initializing Matrix Client for {bot_owner}...")
        
        # Создаем клиента. ВАЖНО: передаем bot_owner как user_id
        client = AsyncClient(
            matrix_server, 
            bot_owner, 
            ssl=matrix_server.startswith("https://")
        )
        client.access_token = access_token
        
        # Записываем данные в глобальный реестр (src/userbot/registry.py)
        # Чтобы другие части бота видели эти настройки
        registry.join_on_invite = join_on_invite
        registry.invite_whitelist = invite_whitelist
        registry.owners = [bot_owner] # Теперь owners не будет пустым списком []

        # Сохраняем экземпляр
        _client_instance = client
        
        # Загружаем модули (если нужно именно здесь)
        from .loader import Loader
        loader = Loader()
        asyncio.run(loader.register_all_modules())

        return _client_instance

    else:
        logger.error("Mandatory config missing: check MATRIX_SERVER, OWNER, and ACCESS_TOKEN")
        sys.exit(1)
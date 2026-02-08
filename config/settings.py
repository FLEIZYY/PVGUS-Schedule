"""Настройки приложения"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота"""
    
    # Токен бота
    BOT_TOKEN: str
    
    # Администраторы
    ADMIN_IDS: str = ""
    
    # База данных
    DATABASE_PATH: str = "data/bot.db"
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/bot.log"
    
    # URL расписания
    SCHEDULE_BASE_URL: str = "https://lk.tolgas.ru/public-schedule"
    SCHEDULE_SEARCH_URL: str = "https://lk.tolgas.ru/public-schedule/search/"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Список ID администраторов"""
        if not self.ADMIN_IDS:
            return []
        return [int(admin_id.strip()) for admin_id in self.ADMIN_IDS.split(",")]


# Создаем глобальный объект настроек
settings = Settings()

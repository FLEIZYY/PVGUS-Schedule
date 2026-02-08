"""Работа с базой данных"""
import aiosqlite
from typing import Optional
from utils.logger import logger


class Database:
    """Упрощенная база данных для хранения настроек пользователей"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def connect(self):
        """Подключение к базе данных"""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.create_tables()
        logger.info(f"База данных подключена: {self.db_path}")
        
    async def disconnect(self):
        """Отключение от базы данных"""
        if hasattr(self, 'connection'):
            await self.connection.close()
            logger.info("База данных отключена")
            
    async def create_tables(self):
        """Создание таблиц"""
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                group_name TEXT,
                notifications_enabled INTEGER DEFAULT 1
            )
        """)
        await self.connection.commit()
        
    async def get_user_group(self, user_id: int) -> Optional[str]:
        """Получение группы пользователя"""
        async with self.connection.execute(
            "SELECT group_name FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['group_name'] if row else None
            
    async def set_user_group(self, user_id: int, username: str, first_name: str, group_name: str):
        """Установка группы пользователя"""
        await self.connection.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, group_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, group_name))
        await self.connection.commit()
        logger.info(f"Группа {group_name} установлена для пользователя {user_id}")
        
    async def get_notifications_enabled(self, user_id: int) -> bool:
        """Проверка включены ли уведомления"""
        async with self.connection.execute(
            "SELECT notifications_enabled FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row['notifications_enabled']) if row else True
            
    async def toggle_notifications(self, user_id: int) -> bool:
        """Переключение уведомлений"""
        enabled = await self.get_notifications_enabled(user_id)
        new_state = not enabled
        
        await self.connection.execute("""
            UPDATE users SET notifications_enabled = ? WHERE user_id = ?
        """, (int(new_state), user_id))
        await self.connection.commit()
        
        logger.info(f"Уведомления для {user_id}: {new_state}")
        return new_state


# Глобальный экземпляр базы данных
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Получить экземпляр базы данных"""
    if _db_instance is None:
        raise RuntimeError("База данных не инициализирована")
    return _db_instance


async def init_db(db_path: str) -> Database:
    """Инициализация базы данных"""
    global _db_instance
    _db_instance = Database(db_path)
    await _db_instance.connect()
    return _db_instance


async def close_db():
    """Закрытие базы данных"""
    global _db_instance
    if _db_instance:
        await _db_instance.disconnect()

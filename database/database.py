"""Работа с базой данных"""
import aiosqlite
from typing import Optional, Dict, Any
from datetime import datetime
import json
from utils.logger import logger


class Database:
    """Упрощенная база данных для хранения настроек пользователей и кэша расписания"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def connect(self):
        """Подключение к базе данных"""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.create_tables()
        logger.info(f"База данных подключена: {self.db_path}")
        
    async def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            await self.connection.close()
            logger.info("База данных отключена")
            self.connection = None
            
    async def create_tables(self):
        """Создание таблиц и индексов"""
        if not self.connection:
            raise RuntimeError("Нет активного соединения с базой данных")
            
        # Таблица пользователей
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                group_name TEXT,
                notifications_enabled INTEGER DEFAULT 1
            )
        """)
        
        # Таблица кэша расписания
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS schedule_cache (
                group_name TEXT NOT NULL,
                date TEXT NOT NULL,                -- 'YYYY-MM-DD'
                data TEXT NOT NULL,                -- JSON строка
                fetched_at INTEGER NOT NULL,       -- unix timestamp
                PRIMARY KEY (group_name, date)
            )
        """)
        
        # Индексы для ускорения
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_date 
            ON schedule_cache (group_name, date)
        """)
        
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_group 
            ON users (group_name)
        """)
        
        await self.connection.commit()
        logger.info("Таблицы и индексы созданы / проверены")
        
    # ────────────────────────────────────────────────
    # Методы для пользователей
    # ────────────────────────────────────────────────
    
    async def get_user_group(self, user_id: int) -> Optional[str]:
        """Получение группы пользователя"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        async with self.connection.execute(
            "SELECT group_name FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['group_name'] if row else None
            
    async def set_user_group(self, user_id: int, username: str, first_name: str, group_name: str):
        """Установка группы пользователя"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        await self.connection.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, group_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, group_name))
        
        await self.connection.commit()
        logger.info(f"Группа {group_name} установлена для пользователя {user_id}")
        
    async def get_notifications_enabled(self, user_id: int) -> bool:
        """Проверка включены ли уведомления"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        async with self.connection.execute(
            "SELECT notifications_enabled FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row['notifications_enabled']) if row else True
            
    async def toggle_notifications(self, user_id: int) -> bool:
        """Переключение состояния уведомлений"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        enabled = await self.get_notifications_enabled(user_id)
        new_state = not enabled
        
        await self.connection.execute("""
            UPDATE users 
            SET notifications_enabled = ? 
            WHERE user_id = ?
        """, (int(new_state), user_id))
        
        await self.connection.commit()
        
        logger.info(f"Уведомления для {user_id}: {'включены' if new_state else 'выключены'}")
        return new_state

    async def get_users_with_notifications(self):
        """
        Возвращает список пользователей с включёнными уведомлениями
        Возвращает: список объектов Row с полями user_id, group_name
        """
        if not self.connection:
            raise RuntimeError("Нет соединения с базой данных")

        cursor = await self.connection.execute("""
            SELECT user_id, group_name 
            FROM users 
            WHERE notifications_enabled = 1 
              AND group_name IS NOT NULL
        """)

        rows = await cursor.fetchall()
        logger.info(f"Найдено {len(rows)} пользователей с включёнными уведомлениями")

        return rows
    
    # ────────────────────────────────────────────────
    # Методы для кэша расписания
    # ────────────────────────────────────────────────
    
    async def get_cached_schedule(self, group_name: str, date: str) -> Optional[Dict[str, Any]]:
        """Получить расписание из кэша, если оно не устарело"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        row = await self.connection.fetchrow("""
            SELECT data, fetched_at 
            FROM schedule_cache 
            WHERE group_name = ? AND date = ?
        """, (group_name, date))
        
        if not row:
            return None
            
        age_hours = (datetime.now().timestamp() - row['fetched_at']) / 3600
        
        # Кэш живёт 12 часов (можно изменить)
        if age_hours > 12:
            await self.delete_cache_entry(group_name, date)
            return None
            
        try:
            return json.loads(row['data'])
        except json.JSONDecodeError as e:
            logger.warning(f"Повреждённый кэш для {group_name} {date}: {e}")
            await self.delete_cache_entry(group_name, date)
            return None


    async def save_schedule_to_cache(self, group_name: str, date: str, schedule_data: Dict[str, Any]):
        """Сохранить расписание в кэш"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        json_data = json.dumps(schedule_data, ensure_ascii=False)
        now = int(datetime.now().timestamp())
        
        await self.connection.execute("""
            INSERT OR REPLACE INTO schedule_cache 
            (group_name, date, data, fetched_at)
            VALUES (?, ?, ?, ?)
        """, (group_name, date, json_data, now))
        
        await self.connection.commit()
        logger.debug(f"Кэш сохранён: {group_name} → {date}")


    async def delete_cache_entry(self, group_name: str, date: str):
        """Удалить конкретную запись кэша"""
        if not self.connection:
            return
            
        await self.connection.execute("""
            DELETE FROM schedule_cache 
            WHERE group_name = ? AND date = ?
        """, (group_name, date))
        
        await self.connection.commit()


    async def clear_old_cache(self, days: int = 14):
        """Очистка записей старше указанного количества дней"""
        if not self.connection:
            raise RuntimeError("Нет соединения с БД")
            
        threshold = int((datetime.now() - timedelta(days=days)).timestamp())
        
        cursor = await self.connection.execute("""
            DELETE FROM schedule_cache 
            WHERE fetched_at < ?
        """, (threshold,))
        
        deleted = cursor.rowcount
        await self.connection.commit()
        
        logger.info(f"Очищено {deleted} старых записей кэша (старше {days} дней)")


# Глобальный экземпляр
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Получить экземпляр базы данных"""
    global _db_instance
    if _db_instance is None:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db()")
    return _db_instance


async def init_db(db_path: str) -> Database:
    """Инициализация базы данных"""
    global _db_instance
    _db_instance = Database(db_path)
    await _db_instance.connect()
    return _db_instance


async def close_db():
    """Закрытие соединения с базой данных"""
    global _db_instance
    if _db_instance:
        await _db_instance.disconnect()
        _db_instance = None
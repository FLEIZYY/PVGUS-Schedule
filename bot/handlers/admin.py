from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from datetime import datetime, timedelta
import asyncio

from database import get_db
from services import ScheduleParser, ScheduleFormatter, ScheduleImageGenerator
from utils.logger import logger
from config import settings

admin_router = Router()


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (только для админов)"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    db = get_db()
    
    # Подсчет статистики
    total_users = await db.connection.execute("SELECT COUNT(*) FROM users")
    total_users = (await total_users.fetchone())[0]
    
    users_with_group = await db.connection.execute(
        "SELECT COUNT(*) FROM users WHERE group_name IS NOT NULL"
    )
    users_with_group = (await users_with_group.fetchone())[0]
    
    users_with_notifications = await db.connection.execute(
        "SELECT COUNT(*) FROM users WHERE notifications_enabled = 1"
    )
    users_with_notifications = (await users_with_notifications.fetchone())[0]
    
    cache_size = await db.connection.execute("SELECT COUNT(*) FROM schedule_cache")
    cache_size = (await cache_size.fetchone())[0]
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ С выбранной группой: {users_with_group}\n"
        f"🔔 С уведомлениями: {users_with_notifications}\n"
        f"💾 Записей в кэше: {cache_size}\n"
    )
    
    await message.answer(stats_text)


@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Рассылка сообщений всем пользователям"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    # Получаем текст для рассылки
    text = message.text.replace("/broadcast", "").strip()
    
    if not text:
        await message.answer(
            "Использование:\n"
            "/broadcast <текст сообщения>\n\n"
            "Пример:\n"
            "/broadcast Уважаемые студенты! Завтра расписание изменено."
        )
        return
    
    db = get_db()
    
    # Получаем всех пользователей
    users_query = await db.connection.execute("SELECT user_id FROM users")
    users = await users_query.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await message.bot.send_message(user[0], text)
            sent += 1
            await asyncio.sleep(0.05)  # Защита от флуда
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки рассылки {user[0]}: {e}")
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )


@admin_router.message(Command("clear_cache"))
async def cmd_clear_cache(message: Message):
    """Очистка кэша расписания"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    db = get_db()
    await db.clear_old_cache(days=0)  # Очистить весь кэш
    await message.answer("✅ Кэш расписания очищен")

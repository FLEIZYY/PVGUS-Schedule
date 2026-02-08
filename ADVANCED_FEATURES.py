"""
ДОПОЛНИТЕЛЬНЫЙ ФУНКЦИОНАЛ

Этот файл содержит примеры дополнительных возможностей:
1. Система уведомлений
2. Админ команды
3. Статистика

Добавьте эти функции в соответствующие файлы для расширения бота.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timedelta
import asyncio

from database import db
from services import ScheduleParser, ScheduleFormatter
from utils.logger import logger
from config import settings


# ==================== УВЕДОМЛЕНИЯ ====================

async def send_morning_notifications(bot: Bot):
    """
    Отправка утренних уведомлений о расписании на сегодня
    
    Добавьте вызов этой функции в main.py через asyncio.create_task()
    """
    while True:
        try:
            now = datetime.now()
            
            # Отправляем уведомления в 7:00
            if now.hour == 7 and now.minute == 0:
                users = await db.get_users_with_notifications()
                
                async with ScheduleParser() as parser:
                    for user in users:
                        try:
                            schedule = await parser.get_schedule(user.group_name)
                            
                            if schedule["lessons"]:
                                text = "🌅 <b>Доброе утро!</b>\n\n"
                                text += ScheduleFormatter.format_day_schedule(schedule)
                                
                                await bot.send_message(
                                    user.user_id,
                                    text
                                )
                                
                                logger.info(f"Отправлено утреннее уведомление для {user.user_id}")
                                
                                # Задержка между отправками
                                await asyncio.sleep(0.5)
                                
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления для {user.user_id}: {e}")
                
                # Ждем следующего дня
                await asyncio.sleep(86400)
            else:
                # Проверяем каждую минуту
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"Ошибка в системе уведомлений: {e}")
            await asyncio.sleep(60)


async def send_lesson_reminders(bot: Bot):
    """
    Отправка напоминаний за 15 минут до начала пары
    """
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Время начала пар
            lesson_times = {
                1: "08:30",
                2: "10:10",
                3: "12:00",
                4: "13:50",
                5: "15:30",
                6: "17:10"
            }
            
            # Проверяем, не за 15 минут ли до начала пары
            for number, time in lesson_times.items():
                lesson_start = datetime.strptime(time, "%H:%M")
                reminder_time = lesson_start - timedelta(minutes=15)
                
                if current_time == reminder_time.strftime("%H:%M"):
                    users = await db.get_users_with_notifications()
                    
                    async with ScheduleParser() as parser:
                        for user in users:
                            try:
                                schedule = await parser.get_schedule(user.group_name)
                                
                                # Ищем занятие с этим номером
                                for lesson in schedule.get("lessons", []):
                                    if lesson["number"] == number:
                                        text = (
                                            f"⏰ <b>Напоминание!</b>\n\n"
                                            f"Через 15 минут начнется {number} пара:\n"
                                            f"📚 {lesson['name']}\n"
                                            f"🕐 {lesson['time']}\n"
                                            f"🚪 Аудитория: {lesson['room']}"
                                        )
                                        
                                        await bot.send_message(user.user_id, text)
                                        logger.info(f"Напоминание отправлено для {user.user_id}")
                                        
                                        await asyncio.sleep(0.5)
                                        
                            except Exception as e:
                                logger.error(f"Ошибка напоминания для {user.user_id}: {e}")
            
            # Проверяем каждую минуту
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в системе напоминаний: {e}")
            await asyncio.sleep(60)


# ==================== АДМИН КОМАНДЫ ====================

admin_router = Router()


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (только для админов)"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
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
    
    await db.clear_old_cache(days=0)  # Очистить весь кэш
    await message.answer("✅ Кэш расписания очищен")


# ==================== ИНТЕГРАЦИЯ ====================

"""
ДЛЯ ДОБАВЛЕНИЯ ФУНКЦИЙ В БОТА:

1. В main.py добавьте после создания dp:

   # Регистрируем админ роутер
   dp.include_router(admin_router)
   
   # Запускаем систему уведомлений
   asyncio.create_task(send_morning_notifications(bot))
   asyncio.create_task(send_lesson_reminders(bot))


2. Полный пример main():

async def main():
    await init_db(settings.DATABASE_PATH)
    
    bot = Bot(token=settings.BOT_TOKEN, ...)
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(schedule.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(admin_router)  # <- Добавить
    
    # Запуск уведомлений (ПОСЛЕ создания bot!)
    asyncio.create_task(send_morning_notifications(bot))
    asyncio.create_task(send_lesson_reminders(bot))
    
    await dp.start_polling(bot)


3. Для отключения уведомлений закомментируйте соответствующие строки
"""

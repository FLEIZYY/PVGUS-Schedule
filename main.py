"""Главный файл запуска бота"""
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db, close_db
from bot.handlers import start, schedule, settings as settings_handlers
from utils.logger import logger


async def main():
    """Главная функция"""
    logger.info("Запуск бота...")
    
    # Создаем необходимые директории
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    # Инициализируем базу данных
    await init_db(settings.DATABASE_PATH)
    logger.info("База данных инициализирована")
    
    # Инициализируем бота и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры (БЕЗ middleware)
    dp.include_router(start.router)
    dp.include_router(schedule.router)
    dp.include_router(settings_handlers.router)
    
    logger.info("Роутеры зарегистрированы")
    
    try:
        # Удаляем вебхук (если был)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удален")
        
        # Запускаем polling
        logger.info("Бот запущен и готов к работе!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        
    finally:
        # Закрываем соединения
        await close_db()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        sys.exit(1)

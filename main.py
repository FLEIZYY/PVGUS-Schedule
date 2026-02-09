import asyncio
import sys
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db, close_db, get_db
from bot.handlers import start, schedule, settings as settings_handlers
from bot.handlers.admin import admin_router
from bot.handlers.notification import send_night_notifications
from utils.logger import logger


async def cache_cleanup_task():
    """Фоновая задача: очистка старого кэша раз в сутки ≈ в 4:05 утра"""
    while True:
        try:
            now = datetime.now()
            if now.hour == 4 and now.minute == 5:  # можно изменить время
                db = get_db()
                await db.clear_old_cache(days=14)
                logger.info("Выполнена плановая очистка кэша расписания")
                await asyncio.sleep(82800)  # почти сутки (23 часа)
            else:
                await asyncio.sleep(300)  # проверяем каждые 5 минут
        except Exception as e:
            logger.error(f"Ошибка в задаче очистки кэша: {e}")
            await asyncio.sleep(3600)  # при ошибке ждём час


async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота...")
    logger.info("🎨 Режим отправки: ИЗОБРАЖЕНИЯ с водяным знаком FLEIZY")

    # Создаём необходимые директории
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

    # Регистрируем все роутеры
    dp.include_router(start.router)
    dp.include_router(schedule.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(admin_router)
    logger.info("Все роутеры зарегистрированы (включая админ-панель)")

    # Запускаем фоновые задачи
    asyncio.create_task(send_night_notifications(bot))
    asyncio.create_task(cache_cleanup_task())
    logger.info("Запущены фоновые задачи: вечерние уведомления, очистка кэша")

    try:
        # Удаляем вебхук (если был)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён (если был установлен)")

        logger.info("=" * 60)
        logger.info("🚀 БОТ УСПЕШНО ЗАПУЩЕН")
        logger.info(f"   • Токен:          {'активен' if bot else 'ошибка'}")
        logger.info(f"   • База данных:    {settings.DATABASE_PATH}")
        logger.info(f"   • Режим:          изображения с водяным знаком FLEIZY")

        logger.info(f"   • Уведомления:    вечерние уведомления в 19:00")
        logger.info(f"   • Очистка кэша:   ежедневно в ~4:05")
        logger.info("=" * 60)

        # Запускаем polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Критическая ошибка во время работы бота: {e}")

    finally:
        # Закрываем соединения
        await close_db()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Ошибка при запуске бота: {e}")
        sys.exit(1)
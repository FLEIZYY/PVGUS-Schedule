from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio

from database import get_db
from services import ScheduleParser, ScheduleFormatter, ScheduleImageGenerator
from utils.logger import logger
from config import settings


async def send_night_notifications(bot: Bot):
    """
    Отправка вечерних уведомлений о расписании на завтра в 19:00 MSK (UTC+4 летом / UTC+3 зимой)
    """
    logger.info("Задача вечерних уведомлений запущена (ежедневно в 19:00 MSK)")

    msk_tz = ZoneInfo("Europe/Moscow")

    while True:
        try:
            now = datetime.now(msk_tz)
            current_time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

            logger.debug(f"Проверка времени (MSK): {current_time_str}")

            if now.hour == 18 and now.minute == 0:
                logger.info(f"[{current_time_str}] ВРЕМЯ СРАБОТАЛО (19:00 MSK) — начинаем рассылку")

                db = get_db()
                users = await db.get_users_with_notifications()

                if not users:
                    logger.info("Нет пользователей с включёнными уведомлениями → рассылка пропущена")
                    await asyncio.sleep(86000)
                    continue

                logger.info(f"Начинаем рассылку для {len(users)} пользователей")

                async with ScheduleParser() as parser:
                    image_generator = ScheduleImageGenerator()

                    for user in users:
                        user_id = user['user_id']
                        group_name = user['group_name']

                        logger.debug(f"Обработка пользователя {user_id} (группа {group_name})")

                        try:
                            tomorrow = datetime.now(msk_tz) + timedelta(days=1)
                            tomorrow_str = tomorrow.strftime("%Y-%m-%d")

                            schedule = await parser.get_schedule(
                                group_name,
                                date=tomorrow
                            )

                            if schedule.get("lessons"):
                                image_bytes = image_generator.generate_schedule_image(schedule)

                                photo = BufferedInputFile(
                                    image_bytes.read(),
                                    filename=f"night_schedule_{schedule.get('date', tomorrow_str)}.png"
                                )

                                caption = (
                                    "🌙 <b>Добрый вечер!</b>\n\n"
                                    f"📅 Расписание на завтра ({schedule.get('date', tomorrow_str)})\n"
                                    f"👥 Группа: {group_name}\n\n"
                                    "Готовьтесь к занятиям заранее! 💪"
                                )

                                await bot.send_photo(
                                    user_id,
                                    photo=photo,
                                    caption=caption
                                )

                                logger.info(f"Отправлено вечернее уведомление для {user_id}")

                                await asyncio.sleep(0.7)

                            else:
                                await bot.send_message(
                                    user_id,
                                    "🌙 Добрый вечер!\n\n"
                                    f"Завтра ({tomorrow_str}) занятий нет. Отдыхай! 😴"
                                )
                                logger.info(f"Отправлено сообщение о выходном для {user_id}")
                                await asyncio.sleep(0.7)

                        except Exception as inner_e:
                            logger.error(
                                f"Ошибка при обработке пользователя {user_id} "
                                f"(группа {group_name}): {inner_e}"
                            )

                logger.info("Рассылка завершена")
                await asyncio.sleep(86000)

            else:
                await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Глобальная ошибка в цикле уведомлений: {e}")
            await asyncio.sleep(60)
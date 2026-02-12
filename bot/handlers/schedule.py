"""Обработчики расписания"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, timezone
from bot.keyboards import inline
from database import get_db
from services import ScheduleParser, ScheduleFormatter, ScheduleImageGenerator
from utils.logger import logger

router = Router()

# UTC+4 (Москва / Самара и др. без летнего времени)
MOSCOW_TZ = timezone(timedelta(hours=4))


@router.callback_query(F.data == "menu_schedule")
async def menu_schedule(callback: CallbackQuery):
    """Меню расписания"""
    db = get_db()
    group_name = await db.get_user_group(callback.from_user.id)
   
    if not group_name:
        await callback.answer(
            "⚠️ Сначала выбери группу в настройках!",
            show_alert=True
        )
        return
   
    text = (
        f"📅 <b>Расписание</b>\n\n"
        f"👥 Группа: {group_name}\n\n"
        f"Выбери период:"
    )
   
    # Если это сообщение с фото — удаляем и отправляем новое
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            text,
            reply_markup=inline.get_schedule_menu()
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=inline.get_schedule_menu()
        )
    await callback.answer()


@router.callback_query(F.data.in_(["schedule_today", "schedule_tomorrow"]))
@router.message(F.text.in_(["📅 Сегодня", "📆 Завтра"]))
async def show_day_schedule(event: Message | CallbackQuery):
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    user_id = event.from_user.id
   
    if is_callback:
        is_tomorrow = event.data == "schedule_tomorrow"
    else:
        is_tomorrow = event.text == "📆 Завтра"
   
    # Берём текущее время в UTC+4
    now = datetime.now(MOSCOW_TZ)
    date = now.date()
   
    if is_tomorrow:
        date += timedelta(days=1)
   
    db = get_db()
    group_name = await db.get_user_group(user_id)
   
    if not group_name:
        text = "⚠️ Сначала выбери группу в настройках!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message.answer(text, reply_markup=inline.get_main_menu())
        return
   
    # Показываем лоадер
    loader_text = "⏳ Генерирую расписание..."
    if is_callback:
        await message.edit_text(loader_text)
    else:
        await message.answer(loader_text)
        # Для message из обычного текста оставляем message как есть
   
    try:
        async with ScheduleParser() as parser:
            schedule_data = await parser.get_schedule(group_name, date=date)
       
        image_generator = ScheduleImageGenerator()
        image_bytes = image_generator.generate_schedule_image(schedule_data)
       
        photo = BufferedInputFile(
            image_bytes.read(),
            filename=f"schedule_{schedule_data.get('date', 'unknown')}.png"
        )
       
        caption = f"📅 Расписание на {schedule_data.get('date', '')}\n👥 Группа: {group_name}"
       
        # Удаляем сообщение с лоадером
        await message.delete()
       
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=inline.get_back_button("menu_schedule")
        )
       
    except Exception as e:
        logger.error(f"Ошибка при генерации расписания на день: {e}")
        await message.delete()
        await message.answer(
            "❌ Ошибка загрузки расписания. Попробуй позже.",
            reply_markup=inline.get_back_button("menu_schedule")
        )


@router.callback_query(F.data == "schedule_week")
@router.message(F.text == "📋 Неделя")
async def show_week_schedule(event: Message | CallbackQuery):
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    user_id = event.from_user.id
   
    db = get_db()
    group_name = await db.get_user_group(user_id)
   
    if not group_name:
        text = "⚠️ Сначала выбери группу в настройках!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message.answer(text, reply_markup=inline.get_main_menu())
        return
   
    # Показываем лоадер
    loader_text = "⏳ Генерирую расписание на неделю..."
    if is_callback:
        await message.edit_text(loader_text)
    else:
        await message.answer(loader_text)
   
    try:
        async with ScheduleParser() as parser:
            week_data = await parser.get_week_schedule(group_name)
       
        image_generator = ScheduleImageGenerator()
       
        media_group = []
       
        for day_schedule in week_data:
            date_str = day_schedule.get('date', '—')
            day_of_week = day_schedule.get('day_of_week', '—')
           
            caption = f"📅 {date_str} — {day_of_week}\n👥 Группа: {group_name}"
           
            image_bytes = image_generator.generate_schedule_image(day_schedule)
           
            media_group.append(
                InputMediaPhoto(
                    media=BufferedInputFile(
                        image_bytes.read(),
                        filename=f"schedule_{date_str}.png"
                    ),
                    caption=caption
                )
            )
       
        # Удаляем лоадер
        await message.delete()
       
        if media_group:
            await message.answer_media_group(media=media_group)
            await message.answer(
                "📋 Расписание на неделю загружено!",
                reply_markup=inline.get_back_button("menu_schedule")
            )
        else:
            await message.answer(
                "На эту неделю расписание отсутствует 😔",
                reply_markup=inline.get_back_button("menu_schedule")
            )
       
    except Exception as e:
        logger.error(f"Ошибка при генерации расписания на неделю: {e}")
        try:
            await message.delete()
        except:
            pass
        await message.answer(
            "❌ Ошибка загрузки расписания. Попробуй позже.",
            reply_markup=inline.get_back_button("menu_schedule")
        )
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
    user_id = callback.from_user.id

    group_name = await db.get_user_group(user_id)
    role = await db.get_user_role(user_id)

    if not group_name:
        await callback.answer(
            "⚠️ Сначала выбери группу в настройках!",
            show_alert=True
        )
        return

    role_title = "Группа" if role == "student" else "Преподаватель"

    text = (
        f"📅 <b>Расписание</b>\n\n"
        f"👤 {role_title}: {group_name}\n\n"
        f"Выбери период:"
    )

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

    now = datetime.now(MOSCOW_TZ)
    date = now.date()

    if is_tomorrow:
        date += timedelta(days=1)

    db = get_db()
    group_name = await db.get_user_group(user_id)
    role = await db.get_user_role(user_id)   # ✅ ДОБАВЛЕНО

    if not group_name:
        text = "⚠️ Сначала выбери группу в настройках!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message.answer(text, reply_markup=inline.get_main_menu())
        return

    loader_text = "⏳ Генерирую расписание..."
    if is_callback:
        await message.edit_text(loader_text)
    else:
        await message.answer(loader_text)

    try:
        date_str = date.strftime("%Y-%m-%d")
        schedule_data = await db.get_cached_schedule(group_name, date_str)
        
        if not schedule_data:
            logger.info(f"📦 Кэш пуст. Запускаем парсер для: {group_name}")
            async with ScheduleParser() as parser:
                schedule_data = await parser.get_schedule(group_name, date=date, role=role)
            await db.save_schedule_to_cache(group_name, date_str, schedule_data)
        else:
            logger.info(f"💾 Данные взяты из кэша для: {group_name}")
            
        # ПРИНУДИТЕЛЬНО ДОБАВЛЯЕМ РОЛЬ В ДАННЫЕ ДЛЯ КАРТИНКИ
        schedule_data['role'] = role
       
        image_generator = ScheduleImageGenerator()
        image_bytes = image_generator.generate_schedule_image(schedule_data)
       
        photo = BufferedInputFile(
            image_bytes.read(),
            filename=f"schedule_{schedule_data.get('date', 'unknown')}.png"
        )
       
        # ДИНАМИЧЕСКАЯ ПОДПИСЬ
        role_title = "Группа" if role == "student" else "Преподаватель"
        caption = f"📅 Расписание на {schedule_data.get('date', '')}\n👤 {role_title}: {group_name}"
       
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
    role = await db.get_user_role(user_id)
   
    if not group_name:
        text = "⚠️ Сначала выбери группу/преподавателя в настройках!"
        if is_callback:
            await event.answer(text, show_alert=True)
        else:
            await message.answer(text, reply_markup=inline.get_main_menu())
        return
   
    loader_text = "⏳ Генерирую расписание на неделю..."
    if is_callback:
        await message.edit_text(loader_text)
    else:
        try: await message.delete() # Удаляем слово "📋 Неделя"
        except: pass
        message = await message.answer(loader_text)
   
    try:
        # 1. Вычисляем даты недели
        now = datetime.now(MOSCOW_TZ)
        start_date = now.date() - timedelta(days=now.weekday())
        dates_to_check = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        
        # 2. Проверяем кэш для каждого дня недели
        week_data = []
        missing_dates = []
        
        for date_str in dates_to_check:
            cached_day = await db.get_cached_schedule(group_name, date_str)
            if cached_day:
                cached_day['role'] = role # Принудительно ставим роль для картинки
                week_data.append(cached_day)
            else:
                missing_dates.append(date_str)
                
        # 3. Если хоть одного дня нет в кэше — парсим всю неделю целиком
        if missing_dates:
            logger.info(f"📦 Кэш недели неполный. Запускаем парсер для: {group_name}")
            async with ScheduleParser() as parser:
                parsed_week = await parser.get_week_schedule(group_name, start_date=start_date, role=role)
            
            # Сохраняем распарсенные дни в кэш и формируем итоговый список
            week_data = []
            for day_schedule in parsed_week:
                day_date_str = day_schedule.get('date')
                if day_date_str:
                    await db.save_schedule_to_cache(group_name, day_date_str, day_schedule)
                day_schedule['role'] = role
                week_data.append(day_schedule)
        else:
            logger.info(f"💾 Неделя полностью взята из кэша для: {group_name}")
            
        # 4. Генерируем картинки
        image_generator = ScheduleImageGenerator()
        media_group = []
        role_title = "Группа" if role == "student" else "Преподаватель"
       
        for day_schedule in week_data:
            # Если в этот день нет пар, мы его пропускаем в карусели (или можешь убрать if, чтобы генерировались пустые дни)
            if not day_schedule.get('lessons'):
                continue
                
            date_str = day_schedule.get('date', '—')
            day_of_week = day_schedule.get('day_of_week', '—')
            caption = f"📅 {date_str} — {day_of_week}\n👤 {role_title}: {group_name}"
           
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
       
        await message.delete()
       
        if media_group:
            await message.answer_media_group(media=media_group)
            await message.answer("📋 Расписание на неделю загружено!", reply_markup=inline.get_back_button("menu_schedule"))
        else:
            await message.answer("На эту неделю расписание отсутствует 😔", reply_markup=inline.get_back_button("menu_schedule"))
       
    except Exception as e:
        logger.error(f"Ошибка при генерации расписания на неделю: {e}")
        try: await message.delete()
        except: pass
        await message.answer("❌ Ошибка загрузки расписания. Попробуй позже.", reply_markup=inline.get_back_button("menu_schedule"))
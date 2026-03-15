"""Обработчики расписания"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta, timezone
from bot.keyboards import inline
from bot.states.schedule import ScheduleStates
from database import get_db
from services import ScheduleParser, ScheduleFormatter, ScheduleImageGenerator
from utils.logger import logger

router = Router()

# UTC+4 (Москва / Самара и др. без летнего времени)
MOSCOW_TZ = timezone(timedelta(hours=4))


@router.callback_query(F.data == "menu_schedule")
async def menu_schedule(callback: CallbackQuery, state: FSMContext):
    """Меню расписания"""
    # Сбрасываем состояние, если пользователь вернулся
    await state.clear()
    
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


@router.callback_query(F.data == "schedule_period")
async def start_period_selection(callback: CallbackQuery, state: FSMContext):
    """Начало выбора периода"""
    db = get_db()
    user_id = callback.from_user.id

    group_name = await db.get_user_group(user_id)

    if not group_name:
        await callback.answer(
            "⚠️ Сначала выбери группу в настройках!",
            show_alert=True
        )
        return

    bot_msg = await callback.message.edit_text(
        "📅 Введите дату начала периода в формате ДД.ММ (например, 03.05):",
        reply_markup=inline.get_back_button("menu_schedule")
    )

    await state.set_state(ScheduleStates.waiting_for_start_date)
    await state.update_data(bot_message_id=bot_msg.message_id)

    await callback.answer()


@router.message(ScheduleStates.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Обработка даты начала"""
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    try:
        # Парсим дату в формате ДД.ММ
        day, month = map(int, message.text.split('.'))
        now = datetime.now(MOSCOW_TZ)
        start_date = datetime(now.year, month, day, tzinfo=MOSCOW_TZ).date()
        
        # Если дата в прошлом году, добавляем год
        if start_date < now.date():
            start_date = start_date.replace(year=now.year + 1)

        # Удаляем сообщение пользователя, чтобы чат оставался чистым
        try:
            await message.delete()
        except Exception:
            pass

        prompt_text = (
            f"✅ Дата начала: {start_date.strftime('%d.%m.%Y')}\n\n"
            "📅 Теперь введите дату окончания периода в формате ДД.ММ:"
        )

        if bot_message_id:
            try:
                await message.bot.edit_message_text(
                    prompt_text,
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=inline.get_back_button("menu_schedule")
                )
            except Exception:
                # Если не удалось отредактировать — просто отправим новое сообщение
                await message.answer(prompt_text, reply_markup=inline.get_back_button("menu_schedule"))
        else:
            await message.answer(prompt_text, reply_markup=inline.get_back_button("menu_schedule"))

        await state.update_data(start_date=start_date)
        await state.set_state(ScheduleStates.waiting_for_end_date)
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате ДД.ММ (например, 03.05):",
            reply_markup=inline.get_back_button("menu_schedule")
        )


@router.message(ScheduleStates.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Обработка даты окончания и генерация расписания за период"""
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    try:
        # Парсим дату окончания
        day, month = map(int, message.text.split('.'))
        now = datetime.now(MOSCOW_TZ)
        end_date = datetime(now.year, month, day, tzinfo=MOSCOW_TZ).date()
        
        # Если дата в прошлом году, добавляем год
        if end_date < now.date():
            end_date = end_date.replace(year=now.year + 1)
        
        start_date = data.get('start_date')
        
        if end_date < start_date:
            await message.answer(
                "❌ Дата окончания не может быть раньше даты начала. Попробуйте снова:",
                reply_markup=inline.get_back_button("menu_schedule")
            )
            return
        
        # Проверяем, что период не слишком длинный (например, не больше 31 дня)
        if (end_date - start_date).days > 31:
            await message.answer(
                "❌ Период не может быть длиннее 31 дня. Выберите меньший период:",
                reply_markup=inline.get_back_button("menu_schedule")
            )
            return

        # Удаляем сообщение пользователя, чтобы чат оставался чистым
        try:
            await message.delete()
        except Exception:
            pass

        # Показываем, что идёт генерация (редактируем предыдущее сообщение)
        if bot_message_id:
            try:
                await message.bot.edit_message_text(
                    f"⏳ Генерирую расписание с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')}...",
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=inline.get_back_button("menu_schedule")
                )
            except Exception:
                pass

        await state.clear()
        
        # Генерируем расписание за период
        await generate_period_schedule(message, start_date, end_date, bot_message_id=bot_message_id)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате ДД.ММ (например, 10.05):",
            reply_markup=inline.get_back_button("menu_schedule")
        )


async def generate_period_schedule(message: Message, start_date: datetime.date, end_date: datetime.date, bot_message_id: int | None = None):
    """Генерация расписания за выбранный период"""
    user_id = message.from_user.id
    db = get_db()
    group_name = await db.get_user_group(user_id)
    role = await db.get_user_role(user_id)
    
    # Убираем сообщение-подсказку (если оно осталось)
    if bot_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=bot_message_id)
        except Exception:
            pass

    loader_text = f"⏳ Генерирую расписание с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')}..."
    loader_msg = await message.answer(loader_text)

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


@router.message(ScheduleStates.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Обработка даты начала"""
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    try:
        # Парсим дату в формате ДД.ММ
        day, month = map(int, message.text.split('.'))
        now = datetime.now(MOSCOW_TZ)
        start_date = datetime(now.year, month, day, tzinfo=MOSCOW_TZ).date()
        
        # Если дата в прошлом году, добавляем год
        if start_date < now.date():
            start_date = start_date.replace(year=now.year + 1)

        # Удаляем сообщение пользователя, чтобы чат оставался чистым
        try:
            await message.delete()
        except Exception:
            pass

        prompt_text = (
            f"✅ Дата начала: {start_date.strftime('%d.%m.%Y')}\n\n"
            "📅 Теперь введите дату окончания периода в формате ДД.ММ:"
        )

        if bot_message_id:
            try:
                await message.bot.edit_message_text(
                    prompt_text,
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=inline.get_back_button("menu_schedule")
                )
            except Exception:
                await message.answer(prompt_text, reply_markup=inline.get_back_button("menu_schedule"))
        else:
            await message.answer(prompt_text, reply_markup=inline.get_back_button("menu_schedule"))

        await state.update_data(start_date=start_date)
        await state.set_state(ScheduleStates.waiting_for_end_date)
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате ДД.ММ (например, 03.05):",
            reply_markup=inline.get_back_button("menu_schedule")
        )


@router.message(ScheduleStates.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Обработка даты окончания и генерация расписания за период"""
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    try:
        # Парсим дату окончания
        day, month = map(int, message.text.split('.'))
        now = datetime.now(MOSCOW_TZ)
        end_date = datetime(now.year, month, day, tzinfo=MOSCOW_TZ).date()
        
        # Если дата в прошлом году, добавляем год
        if end_date < now.date():
            end_date = end_date.replace(year=now.year + 1)
        
        start_date = data.get('start_date')
        
        if end_date < start_date:
            await message.answer(
                "❌ Дата окончания не может быть раньше даты начала. Попробуйте снова:",
                reply_markup=inline.get_back_button("menu_schedule")
            )
            return
        
        # Проверяем, что период не слишком длинный (например, не больше 31 дня)
        if (end_date - start_date).days > 31:
            await message.answer(
                "❌ Период не может быть длиннее 31 дня. Выберите меньший период:",
                reply_markup=inline.get_back_button("menu_schedule")
            )
            return

        # Удаляем сообщение пользователя, чтобы чат оставался чистым
        try:
            await message.delete()
        except Exception:
            pass

        # Показываем, что идёт генерация (редактируем предыдущее сообщение)
        if bot_message_id:
            try:
                await message.bot.edit_message_text(
                    f"⏳ Генерирую расписание с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')}...",
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=inline.get_back_button("menu_schedule")
                )
            except Exception:
                pass

        await state.clear()
        
        # Генерируем расписание за период
        await generate_period_schedule(message, start_date, end_date, bot_message_id=bot_message_id)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате ДД.ММ (например, 10.05):",
            reply_markup=inline.get_back_button("menu_schedule")
        )


async def generate_period_schedule(message: Message, start_date: datetime.date, end_date: datetime.date, bot_message_id: int | None = None):
    """Генерация расписания за выбранный период"""
    user_id = message.from_user.id
    db = get_db()
    group_name = await db.get_user_group(user_id)
    role = await db.get_user_role(user_id)
    
    # Убираем сообщение-подсказку (если оно осталось)
    if bot_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=bot_message_id)
        except Exception:
            pass

    loader_text = f"⏳ Генерирую расписание с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')}..."
    loader_msg = await message.answer(loader_text)
    
    try:
        # Собираем все даты в периоде
        dates_to_check = []
        current_date = start_date
        while current_date <= end_date:
            dates_to_check.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        
        # Проверяем кэш для каждого дня
        period_data = []
        missing_dates = []
        
        for date_str in dates_to_check:
            cached_day = await db.get_cached_schedule(group_name, date_str)
            if cached_day:
                cached_day['role'] = role
                period_data.append(cached_day)
            else:
                missing_dates.append(date_str)
        
        # Если есть пропущенные дни, парсим их
        if missing_dates:
            logger.info(f"📦 Кэш периода неполный. Парсим {len(missing_dates)} дней для: {group_name}")
            async with ScheduleParser() as parser:
                # Парсим каждый пропущенный день
                for date_str in missing_dates:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    day_schedule = await parser.get_schedule(group_name, date=date_obj, role=role)
                    if day_schedule:
                        await db.save_schedule_to_cache(group_name, date_str, day_schedule)
                        day_schedule['role'] = role
                        period_data.append(day_schedule)
        
        # Сортируем по дате
        period_data.sort(key=lambda x: x.get('date', ''))
        
        # Генерируем картинки
        image_generator = ScheduleImageGenerator()
        media_group = []
        role_title = "Группа" if role == "student" else "Преподаватель"
        
        for day_schedule in period_data:
            # Пропускаем дни без пар, если хочешь
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
        
        await loader_msg.delete()
        
        if media_group:
            await message.answer_media_group(media_group)
            await message.answer(
                f"📅 Расписание с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')} загружено!",
                reply_markup=inline.get_back_button("menu_schedule")
            )
        else:
            await message.answer(
                f"На период с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')} расписание отсутствует 😔",
                reply_markup=inline.get_back_button("menu_schedule")
            )
    
    except Exception as e:
        logger.error(f"Ошибка при генерации расписания за период: {e}")
        await loader_msg.delete()
        await message.answer(
            "❌ Ошибка загрузки расписания. Попробуй позже.",
            reply_markup=inline.get_back_button("menu_schedule")
        )
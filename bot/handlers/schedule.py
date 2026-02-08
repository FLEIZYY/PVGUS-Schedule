"""Обработчики расписания"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from bot.keyboards import inline
from database import get_db
from services import ScheduleParser, ScheduleFormatter
from utils.logger import logger

router = Router()


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
    
    await callback.message.edit_text(
        f"📅 <b>Расписание</b>\n\n"
        f"👥 Группа: {group_name}\n\n"
        f"Выбери период:",
        reply_markup=inline.get_schedule_menu()
    )
    await callback.answer()


@router.callback_query(F.data.in_(["schedule_today", "schedule_tomorrow"]))
@router.message(F.text.in_(["📅 Сегодня", "📆 Завтра"]))
async def show_day_schedule(event: Message | CallbackQuery):
    """Показать расписание на день"""
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    user_id = event.from_user.id
    
    if is_callback:
        is_tomorrow = event.data == "schedule_tomorrow"
    else:
        is_tomorrow = event.text == "📆 Завтра"
    
    date = datetime.now()
    if is_tomorrow:
        date += timedelta(days=1)
    
    db = get_db()
    group_name = await db.get_user_group(user_id)
    
    if not group_name:
        if is_callback:
            await event.answer("⚠️ Сначала выбери группу в настройках!", show_alert=True)
        else:
            await message.answer(
                "⚠️ Сначала выбери группу в настройках!",
                reply_markup=inline.get_main_menu()
            )
        return
    
    if is_callback:
        await event.answer("Загружаю расписание...")
    else:
        loading_msg = await message.answer("⏳ Загружаю расписание...")
    
    try:
        async with ScheduleParser() as parser:
            schedule_data = await parser.get_schedule(group_name, date)
        
        text = ScheduleFormatter.format_day_schedule(schedule_data)
        
        if is_callback:
            await message.edit_text(
                text,
                reply_markup=inline.get_back_button("menu_schedule")
            )
        else:
            await loading_msg.delete()
            await message.answer(
                text,
                reply_markup=inline.get_back_button("menu_schedule")
            )
            
    except Exception as e:
        logger.error(f"Ошибка получения расписания: {e}")
        error_text = "❌ Ошибка загрузки расписания. Попробуй позже."
        
        if is_callback:
            await event.answer(error_text, show_alert=True)
        else:
            await loading_msg.edit_text(error_text)


@router.callback_query(F.data == "schedule_week")
@router.message(F.text == "📋 Неделя")
async def show_week_schedule(event: Message | CallbackQuery):
    """Показать расписание на неделю"""
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    user_id = event.from_user.id
    
    db = get_db()
    group_name = await db.get_user_group(user_id)
    
    if not group_name:
        if is_callback:
            await event.answer("⚠️ Сначала выбери группу в настройках!", show_alert=True)
        else:
            await message.answer(
                "⚠️ Сначала выбери группу в настройках!",
                reply_markup=inline.get_main_menu()
            )
        return
    
    if is_callback:
        await event.answer("Загружаю расписание на неделю...")
        loading_msg = await message.answer("⏳ Загружаю расписание на неделю...")
    else:
        loading_msg = await message.answer("⏳ Загружаю расписание на неделю...")
    
    try:
        async with ScheduleParser() as parser:
            week_data = await parser.get_week_schedule(group_name)
        
        messages = ScheduleFormatter.format_week_schedule(week_data)
        
        await loading_msg.delete()
        
        for msg_text in messages:
            await message.answer(msg_text)
        
        await message.answer(
            "📋 Расписание на неделю загружено!",
            reply_markup=inline.get_back_button("menu_schedule")
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения недельного расписания: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка загрузки расписания. Попробуй позже.",
            reply_markup=inline.get_back_button("menu_schedule")
        )

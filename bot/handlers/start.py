"""Обработчики команд /start и /help"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import inline
from database import get_db
from utils.logger import logger

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    db = get_db()
    group_name = await db.get_user_group(message.from_user.id)
    
    if group_name:
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
            f"👥 Твоя группа: <b>{group_name}</b>\n\n"
            f"Выбери действие:",
            reply_markup=inline.get_main_menu()
        )
    else:
        await message.answer(
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Я бот для просмотра расписания ПВГУС.\n\n"
            f"Для начала работы выбери свою группу в настройках.",
            reply_markup=inline.get_main_menu()
        )
    
    logger.info(f"Пользователь {message.from_user.id} запустил бота")


@router.message(Command("help"))
@router.message(F.text.in_(["ℹ️ Помощь", "Помощь"]))
async def cmd_help(message: Message):
    """Обработка команды /help"""
    help_text = (
        "📖 <b>Помощь по боту</b>\n\n"
        
        "<b>Основные команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Показать эту справку\n\n"
        
        "<b>Быстрые кнопки:</b>\n"
        "📅 Сегодня - расписание на сегодня\n"
        "📆 Завтра - расписание на завтра\n"
        "📋 Неделя - расписание на неделю\n"
        "⚙️ Настройки - настройки бота\n\n"
        
        "<b>Настройки:</b>\n"
        "• Выбор группы\n"
        "• Включение/выключение уведомлений\n\n"
        
        "Расписание берётся с сайта ПВГУС\n"
        "https://lk.tolgas.ru/public-schedule/"
    )
    
    await message.answer(
        help_text,
        reply_markup=inline.get_back_button("back_to_main")
    )


@router.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    """Информация о боте"""
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        
        "🎓 Бот расписания ПВГУС\n"
        "Версия: 1.0.0\n\n"
        
        "Бот помогает студентам ПВГУС быстро получать актуальное "
        "расписание занятий прямо в Telegram.\n\n"
        
        "Расписание берётся с официального сайта университета: "
        "https://lk.tolgas.ru/public-schedule/"
    )
    
    await callback.message.edit_text(
        info_text,
        reply_markup=inline.get_back_button("back_to_main"),
        disable_web_page_preview=True
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    
    db = get_db()
    group_name = await db.get_user_group(callback.from_user.id)
    
    if group_name:
        text = (
            f"👋 Главное меню\n\n"
            f"👥 Твоя группа: <b>{group_name}</b>\n\n"
            f"Выбери действие:"
        )
    else:
        text = (
            f"👋 Главное меню\n\n"
            f"Для начала работы выбери свою группу в настройках."
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=inline.get_main_menu()
    )
    await callback.answer()

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import inline
from bot.states import SettingsStates
from database import get_db
from services import ScheduleParser
from utils.logger import logger
from config import settings

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    db = get_db()
    
    # Удаляем сообщение пользователя с командой /start для чистоты чата
    try: 
        await message.delete() 
    except: 
        pass

    group_name = await db.get_user_group(message.from_user.id)
    role = await db.get_user_role(message.from_user.id)
    
    if group_name:
        role_text = "Группа" if role == "student" else "Преподаватель"
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
            f"👤 {role_text}: <b>{group_name}</b>\n\n"
            f"Выбери действие:",
            reply_markup=inline.get_main_menu(message.from_user.id, settings.admin_ids_list)
        )
    else:
        # Если новый пользователь - просим выбрать роль
        builder = inline.InlineKeyboardBuilder()
        builder.row(
            inline.InlineKeyboardButton(text="👨‍🎓 Я студент", callback_data="set_role:student"),
            inline.InlineKeyboardButton(text="👨‍🏫 Я преподаватель", callback_data="set_role:teacher")
        )
        await message.answer(
            f"👋 Привет, {message.from_user.first_name}!\n"
            f"Я бот для просмотра расписания ПВГУС.\n\n"
            f"Для начала работы выбери свою роль:",
            reply_markup=builder.as_markup()
        )
    
    logger.info(f"Пользователь {message.from_user.id} запустил бота")

@router.callback_query(F.data.startswith("set_role:"))
async def process_set_role(callback: CallbackQuery, state: FSMContext):
    """Выбор роли и загрузка начального списка"""
    role = callback.data.split(":")[1]
    db = get_db()
    
    # Сохраняем роль
    await db.set_user_group(callback.from_user.id, callback.from_user.username, callback.from_user.first_name, None)
    await db.set_user_role(callback.from_user.id, role)
    
    role_name = "студента" if role == "student" else "преподавателя"
    title_name = "группы" if role == "student" else "преподавателя"
    
    await callback.message.edit_text(f"✅ Выбрана роль {role_name}. Загружаю список...")
    
    await state.update_data(role=role)
    
    try:
        async with ScheduleParser() as parser:
            targets = await parser.search_targets(role=role)
        
        await state.update_data(groups=targets, page=0)
        await state.set_state(SettingsStates.changing_target)
        
        await callback.message.edit_text(
            f"👤 <b>Выбор {title_name}</b>\n\n"
            f"Выбери из списка или используй поиск:",
            reply_markup=inline.get_groups_keyboard(targets, page=0)
        )
    except Exception as e:
        logger.error(f"Ошибка при загрузке начального списка: {e}")
        await callback.message.edit_text("❌ Ошибка загрузки списка. Нажми /start позже.")


@router.message(Command("help"))
@router.message(F.text.in_(["ℹ️ Помощь", "Помощь"]))
async def cmd_help(message: Message):
    """Обработка команды /help"""
    try: await message.delete()
    except: pass
    
    help_text = (
        "📖 <b>Помощь по боту</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Главное меню\n\n"
        "<b>Быстрые кнопки:</b>\n"
        "📅 Сегодня - расписание на сегодня\n"
        "📆 Завтра - расписание на завтра\n"
        "📋 Неделя - расписание на неделю\n"
        "⚙️ Настройки - настройки бота\n\n"
        "Расписание берётся с официального сайта ПВГУС."
    )
    await message.answer(help_text, reply_markup=inline.get_back_button("back_to_main"))


@router.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    """Информация о боте"""
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        
        "🎓 Бот расписания ПВГУС\n"
        "Версия: 2.1.0\n\n"
        
        "Бот помогает студентам ПВГУС быстро получать актуальное "
        "расписание занятий прямо в Telegram.\n\n"
        
        "Расписание берётся с официального сайта университета: "
        "https://lk.tolgas.ru/public-schedule/search/"
    )
    await callback.message.edit_text(info_text, reply_markup=inline.get_back_button("back_to_main"))
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    db = get_db()
    
    group_name = await db.get_user_group(callback.from_user.id)
    role = await db.get_user_role(callback.from_user.id)
    
    if group_name:
        role_text = "Группа" if role == "student" else "Преподаватель"
        text = f"👋 Главное меню\n\n👤 {role_text}: <b>{group_name}</b>\n\nВыбери действие:"
    else:
        text = "👋 Главное меню\n\nДля начала работы выбери свою роль и группу в настройках."
    
    await callback.message.edit_text(
        text, 
        reply_markup=inline.get_main_menu(callback.from_user.id, settings.admin_ids_list)
    )
    await callback.answer()
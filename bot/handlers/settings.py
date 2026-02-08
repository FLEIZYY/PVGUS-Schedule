"""Обработчики настроек"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import inline
from bot.states import SettingsStates
from database import get_db
from services import ScheduleParser
from utils.logger import logger

router = Router()


@router.callback_query(F.data == "menu_settings")
@router.message(F.text == "⚙️ Настройки")
async def menu_settings(event: Message | CallbackQuery):
    """Меню настроек"""
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    user_id = event.from_user.id
    
    db = get_db()
    group_name = await db.get_user_group(user_id)
    notifications_enabled = await db.get_notifications_enabled(user_id)
    
    settings_text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"👥 Группа: <b>{group_name or 'не выбрана'}</b>\n"
        f"🔔 Уведомления: <b>{'включены' if notifications_enabled else 'выключены'}</b>\n\n"
        f"Выбери, что хочешь изменить:"
    )
    
    if is_callback:
        await message.edit_text(
            settings_text,
            reply_markup=inline.get_settings_menu(notifications_enabled)
        )
        await event.answer()
    else:
        await message.answer(
            settings_text,
            reply_markup=inline.get_settings_menu(notifications_enabled)
        )


@router.callback_query(F.data == "settings_group")
async def settings_group(callback: CallbackQuery, state: FSMContext):
    """Изменение группы"""
    await callback.answer("Загружаю список групп...")
    
    try:
        async with ScheduleParser() as parser:
            groups = await parser.search_groups()
        
        if not groups:
            await callback.answer(
                "❌ Не удалось загрузить список групп",
                show_alert=True
            )
            return
        
        await state.update_data(groups=groups, page=0)
        await state.set_state(SettingsStates.changing_group)
        
        await callback.message.edit_text(
            "👥 <b>Выбор группы</b>\n\n"
            "Выбери свою группу из списка или используй поиск:",
            reply_markup=inline.get_groups_keyboard(groups, page=0)
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки групп: {e}")
        await callback.answer(
            "❌ Ошибка загрузки списка групп",
            show_alert=True
        )


@router.callback_query(F.data.startswith("groups_page:"))
async def groups_pagination(callback: CallbackQuery, state: FSMContext):
    """Пагинация списка групп"""
    page = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    groups = data.get("groups", [])
    
    await state.update_data(page=page)
    
    await callback.message.edit_reply_markup(
        reply_markup=inline.get_groups_keyboard(groups, page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_group:"))
async def select_group(callback: CallbackQuery, state: FSMContext):
    """Выбор группы"""
    group_name = callback.data.split(":", 1)[1]
    
    db = get_db()
    await db.set_user_group(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        group_name
    )
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ Группа успешно изменена!\n\n"
        f"👥 Твоя группа: <b>{group_name}</b>\n\n"
        f"Теперь ты можешь просматривать расписание.",
        reply_markup=inline.get_back_button("menu_settings")
    )
    await callback.answer("✅ Группа сохранена!")
    
    logger.info(f"Пользователь {callback.from_user.id} выбрал группу {group_name}")


@router.callback_query(F.data == "search_group")
async def search_group(callback: CallbackQuery, state: FSMContext):
    """Начало поиска группы"""
    await state.set_state(SettingsStates.searching_group)
    
    await callback.message.edit_text(
        "🔍 <b>Поиск группы</b>\n\n"
        "Введи название или номер группы:\n"
        "(например: БОЗИ24 или ПИ-101)",
        reply_markup=inline.get_back_button("settings_group")
    )
    await callback.answer()


@router.message(SettingsStates.searching_group)
async def process_group_search(message: Message, state: FSMContext):
    """Обработка поиска группы"""
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer(
            "⚠️ Запрос слишком короткий. Введи минимум 2 символа.",
            reply_markup=inline.get_back_button("settings_group")
        )
        return
    
    loading_msg = await message.answer("🔍 Ищу группы...")
    
    try:
        async with ScheduleParser() as parser:
            groups = await parser.search_groups(query)
        
        await loading_msg.delete()
        
        if not groups:
            await message.answer(
                f"❌ Группы не найдены по запросу: <b>{query}</b>\n\n"
                f"Попробуй изменить запрос.",
                reply_markup=inline.get_back_button("settings_group")
            )
            return
        
        await state.update_data(groups=groups, page=0)
        await state.set_state(SettingsStates.changing_group)
        
        await message.answer(
            f"🔍 Найдено групп: <b>{len(groups)}</b>\n\n"
            f"Выбери свою группу:",
            reply_markup=inline.get_groups_keyboard(groups, page=0)
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска групп: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка поиска. Попробуй позже.",
            reply_markup=inline.get_back_button("settings_group")
        )


@router.callback_query(F.data == "settings_notifications")
async def toggle_notifications(callback: CallbackQuery):
    """Переключение уведомлений"""
    db = get_db()
    new_state = await db.toggle_notifications(callback.from_user.id)
    
    state_text = "включены ✅" if new_state else "выключены ❌"
    await callback.answer(f"Уведомления {state_text}")
    
    group_name = await db.get_user_group(callback.from_user.id)
    
    settings_text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"👥 Группа: <b>{group_name or 'не выбрана'}</b>\n"
        f"🔔 Уведомления: <b>{'включены' if new_state else 'выключены'}</b>\n\n"
        f"Выбери, что хочешь изменить:"
    )
    
    await callback.message.edit_text(
        settings_text,
        reply_markup=inline.get_settings_menu(new_state)
    )
    
    logger.info(f"Пользователь {callback.from_user.id} изменил уведомления: {new_state}")


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, state: FSMContext):
    """Возврат в настройки"""
    await state.clear()
    await menu_settings(callback)

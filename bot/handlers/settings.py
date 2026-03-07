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
    
    if not is_callback:
        try: await message.delete()
        except: pass
    
    db = get_db()
    group_name = await db.get_user_group(user_id)
    role = await db.get_user_role(user_id)
    notifications_enabled = await db.get_notifications_enabled(user_id)
    
    role_text = "Группа" if role == "student" else "Преподаватель"
    
    settings_text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"👤 {role_text}: <b>{group_name or 'не выбрано'}</b>\n"
        f"🔔 Уведомления: <b>{'включены' if notifications_enabled else 'выключены'}</b>\n\n"
        f"Выбери, что хочешь изменить:"
    )
    
    markup = inline.get_settings_menu(notifications_enabled, role)
    
    if is_callback:
        await message.edit_text(settings_text, reply_markup=markup)
        await event.answer()
    else:
        await message.answer(settings_text, reply_markup=markup)


@router.callback_query(F.data == "settings_group")
async def settings_group(callback: CallbackQuery, state: FSMContext):
    """Изменение группы/преподавателя"""
    await callback.answer("Загружаю список...")
    db = get_db()
    role = await db.get_user_role(callback.from_user.id)
    
    try:
        async with ScheduleParser() as parser:
            targets = await parser.search_targets(role=role)
        
        if not targets:
            await callback.answer("❌ Не удалось загрузить список", show_alert=True)
            return
        
        await state.update_data(groups=targets, page=0, role=role)
        await state.set_state(SettingsStates.changing_target)
        
        title = "группы" if role == "student" else "преподавателя"
        await callback.message.edit_text(
            f"👤 <b>Выбор {title}</b>\n\nВыбери из списка или используй поиск:",
            reply_markup=inline.get_groups_keyboard(targets, page=0)
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки списка: {e}")
        await callback.answer("❌ Ошибка загрузки списка", show_alert=True)


@router.callback_query(F.data.startswith("groups_page:"))
async def groups_pagination(callback: CallbackQuery, state: FSMContext):
    """Пагинация списка"""
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    groups = data.get("groups", [])
    
    await state.update_data(page=page)
    await callback.message.edit_reply_markup(reply_markup=inline.get_groups_keyboard(groups, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("sg:"))
async def select_group(callback: CallbackQuery, state: FSMContext):
    """Выбор группы/преподавателя по индексу"""
    # Получаем индекс из кнопки
    idx = int(callback.data.split(":")[1])
    
    # Достаем список из памяти состояния
    data = await state.get_data()
    groups = data.get("groups", [])
    
    if not groups or idx >= len(groups):
        await callback.answer("❌ Ошибка: список устарел. Повтори поиск.", show_alert=True)
        return
        
    # Получаем реальное длинное имя
    target_name = groups[idx]["name"]
    
    db = get_db()
    await db.set_user_group(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        target_name
    )
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Успешно сохранено!\n\n"
        f"👤 Твой выбор: <b>{target_name}</b>\n\n"
        f"Теперь ты можешь просматривать расписание.",
        reply_markup=inline.get_back_button("menu_settings")
    )
    await callback.answer("✅ Сохранено!")
    logger.info(f"Пользователь {callback.from_user.id} выбрал {target_name}")


@router.callback_query(F.data == "search_group")
async def search_group(callback: CallbackQuery, state: FSMContext):
    """Начало поиска группы"""
    await state.set_state(SettingsStates.searching_target)
    
    db = get_db()
    role = await db.get_user_role(callback.from_user.id)
    
    title = "группы" if role == "student" else "преподавателя"
    example = "название (например: БОЗИ24)" if role == "student" else "ФИО (например: Иванов)"
    
    msg = await callback.message.edit_text(
        f"🔍 <b>Поиск {title}</b>\n\nВведи {example}:\n",
        reply_markup=inline.get_back_button("settings_group")
    )
    
    # Сохраняем ID сообщения, чтобы редактировать его при поиске
    await state.update_data(search_msg_id=msg.message_id, role=role)
    await callback.answer()


@router.message(SettingsStates.searching_target)
async def process_group_search(message: Message, state: FSMContext):
    """Обработка поиска группы (ЧИСТЫЙ ЧАТ)"""
    query = message.text.strip()
    data = await state.get_data()
    search_msg_id = data.get("search_msg_id")
    role = data.get("role", "student")
    
    # Сразу удаляем сообщение пользователя, чтобы чат не засорялся
    try: await message.delete()
    except: pass
    
    if len(query) < 2:
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=search_msg_id,
            text="⚠️ Запрос слишком короткий. Введи минимум 2 символа.",
            reply_markup=inline.get_back_button("settings_group")
        )
        return
    
    await message.bot.edit_message_text(
        chat_id=message.chat.id, message_id=search_msg_id,
        text="🔍 Ищу..."
    )
    
    try:
        async with ScheduleParser() as parser:
            targets = await parser.search_targets(query, role=role)
        
        if not targets:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=search_msg_id,
                text=f"❌ Ничего не найдено по запросу: <b>{query}</b>\n\nПопробуй изменить запрос.",
                reply_markup=inline.get_back_button("settings_group")
            )
            return
        
        await state.update_data(groups=targets, page=0)
        await state.set_state(SettingsStates.changing_target)
        
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=search_msg_id,
            text=f"🔍 Найдено: <b>{len(targets)}</b>\n\nВыбери из списка:",
            reply_markup=inline.get_groups_keyboard(targets, page=0)
        )
        
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id, message_id=search_msg_id,
            text="❌ Ошибка поиска. Попробуй позже.",
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
    role = await db.get_user_role(callback.from_user.id)
    role_text = "Группа" if role == "student" else "Преподаватель"
    
    settings_text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"👤 {role_text}: <b>{group_name or 'не выбрано'}</b>\n"
        f"🔔 Уведомления: <b>{'включены' if new_state else 'выключены'}</b>\n\n"
        f"Выбери, что хочешь изменить:"
    )
    
    await callback.message.edit_text(settings_text, reply_markup=inline.get_settings_menu(new_state))
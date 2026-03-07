from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

from database import get_db
from bot.keyboards import inline
from utils.logger import logger
from config import settings

admin_router = Router()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    broadcast_msg_id = State()

@admin_router.callback_query(F.data == "menu_admin")
async def menu_admin(callback: CallbackQuery, state: FSMContext):
    """Вход в админ-панель"""
    if callback.from_user.id not in settings.admin_ids_list:
        await callback.answer("⛔ У вас нет доступа", show_alert=True)
        return
    
    await state.clear()
    text = "👑 <b>Админ-панель</b>\n\nВыберите действие:"
    await callback.message.edit_text(text, reply_markup=inline.get_admin_menu())

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Статистика бота"""
    if callback.from_user.id not in settings.admin_ids_list: return
    
    db = get_db()
    
    total_users = (await (await db.connection.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
    users_with_group = (await (await db.connection.execute("SELECT COUNT(*) FROM users WHERE group_name IS NOT NULL")).fetchone())[0]
    users_with_notif = (await (await db.connection.execute("SELECT COUNT(*) FROM users WHERE notifications_enabled = 1")).fetchone())[0]
    cache_size = (await (await db.connection.execute("SELECT COUNT(*) FROM schedule_cache")).fetchone())[0]
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ С выбранной ролью: <b>{users_with_group}</b>\n"
        f"🔔 С уведомлениями: <b>{users_with_notif}</b>\n"
        f"💾 Записей в кэше: <b>{cache_size}</b>\n"
    )
    
    await callback.message.edit_text(stats_text, reply_markup=inline.get_back_button("menu_admin"))

@admin_router.callback_query(F.data == "admin_clear_cache")
async def admin_clear_cache(callback: CallbackQuery):
    """Очистка кэша с кнопки"""
    if callback.from_user.id not in settings.admin_ids_list: return
    
    db = get_db()
    await db.clear_old_cache(days=0)
    await callback.answer("✅ Весь кэш расписания очищен!", show_alert=True)

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Подготовка к рассылке"""
    if callback.from_user.id not in settings.admin_ids_list: return
    
    msg = await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте мне сообщение, которое нужно разослать всем пользователям.\n"
        "<i>Можно использовать текст, фото, видео или кружочки.</i>",
        reply_markup=inline.get_back_button("menu_admin")
    )
    
    await state.set_state(AdminStates.waiting_for_broadcast)
    await state.update_data(broadcast_msg_id=msg.message_id)

@admin_router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    """Выполнение рассылки (ЧИСТЫЙ ЧАТ)"""
    data = await state.get_data()
    b_msg_id = data.get("broadcast_msg_id")
    
    await message.bot.edit_message_text("⏳ Начинаю рассылку...", chat_id=message.chat.id, message_id=b_msg_id)
    
    db = get_db()
    users_query = await db.connection.execute("SELECT user_id FROM users")
    users = await users_query.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            # Копируем сообщение пользователю (ДО того как удалим оригинал!)
            await message.copy_to(user[0])
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Ошибка рассылки для {user[0]}: {e}")
            failed += 1
    
    await message.bot.edit_message_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>",
        chat_id=message.chat.id, 
        message_id=b_msg_id,
        reply_markup=inline.get_back_button("menu_admin")
    )
    await state.clear()
    
    # УДАЛЯЕМ СООБЩЕНИЕ АДМИНА ТОЛЬКО В САМОМ КОНЦЕ!
    try: await message.delete()
    except: pass
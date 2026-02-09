"""Inline клавиатуры"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 Расписание", callback_data="menu_schedule"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Информация", callback_data="menu_info"),
        InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/delovoybalik")
    )
    
    return builder.as_markup()


def get_schedule_menu() -> InlineKeyboardMarkup:
    """Меню расписания"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="Сегодня", callback_data="schedule_today"),
        InlineKeyboardButton(text="Завтра", callback_data="schedule_tomorrow")
    )
    builder.row(
        InlineKeyboardButton(text="Неделя", callback_data="schedule_week")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_settings_menu(notifications_enabled: bool = True) -> InlineKeyboardMarkup:
    """Меню настроек"""
    builder = InlineKeyboardBuilder()
    
    notification_text = "🔕 Выкл. уведомления" if notifications_enabled else "🔔 Вкл. уведомления"
    
    builder.row(
        InlineKeyboardButton(text="👥 Сменить группу", callback_data="settings_group")
    )
    builder.row(
        InlineKeyboardButton(text=notification_text, callback_data="settings_notifications")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_groups_keyboard(groups: List[Dict[str, str]], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком групп
    
    Args:
        groups: Список групп
        page: Номер страницы
        per_page: Групп на странице
    """
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_groups = groups[start:end]
    
    for group in page_groups:
        builder.row(
            InlineKeyboardButton(
                text=group["name"],
                callback_data=f"select_group:{group['name']}"
            )
        )
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"groups_page:{page-1}")
        )
    if end < len(groups):
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"groups_page:{page+1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data="search_group"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_settings")
    )
    
    return builder.as_markup()


def get_week_navigation(current_week: int = 0) -> InlineKeyboardMarkup:
    """
    Навигация по неделям
    
    Args:
        current_week: Смещение недели (0 - текущая, 1 - следующая, -1 - предыдущая)
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="◀️ Пред.", callback_data=f"week:{current_week-1}"),
        InlineKeyboardButton(text="Текущая", callback_data="week:0"),
        InlineKeyboardButton(text="След. ▶️", callback_data=f"week:{current_week+1}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu_schedule")
    )
    
    return builder.as_markup()


def get_back_button(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)
    )
    return builder.as_markup()


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия
    
    Args:
        action: Действие для подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{action}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel:{action}")
    )
    
    return builder.as_markup()

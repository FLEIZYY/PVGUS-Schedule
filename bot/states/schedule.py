"""FSM состояния для расписания"""
from aiogram.fsm.state import State, StatesGroup


class ScheduleStates(StatesGroup):
    """Состояния для работы с расписанием"""
    waiting_for_group = State()
    searching_group = State()
    viewing_schedule = State()


class SettingsStates(StatesGroup):
    """Состояния для настроек"""
    changing_group = State()
    searching_group = State()

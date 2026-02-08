"""Форматирование расписания для отображения"""
from typing import Dict, List
from datetime import datetime


class ScheduleFormatter:
    """Форматирование расписания"""
    
    @staticmethod
    def format_day_schedule(schedule: Dict[str, any]) -> str:
        """
        Форматирование расписания на день
        
        Args:
            schedule: Словарь с расписанием
            
        Returns:
            Отформатированная строка
        """
        if not schedule.get("lessons"):
            return (
                f"📅 {schedule['date']} - {schedule['day_of_week']}\n\n"
                f"🎉 <b>РАСПИСАНИЕ ОТСУТСТВУЕТ</b>\n\n"
                f"Занятий в этот день нет!"
            )
            
        text = f"📅 <b>{schedule['date']}</b> - {schedule['day_of_week']}\n"
        text += f"👥 Группа: <b>{schedule['group_name']}</b>\n\n"
        
        for lesson in schedule["lessons"]:
            text += f"━━━━━━━━━━━━━━━━━\n"
            text += f"🔢 <b>{lesson['number']} пара</b> ({lesson['time']})\n"
            text += f"📚 {lesson['name']}\n"
            text += f"📝 Тип: {lesson['type']}\n"
            text += f"👨‍🏫 Преп.: {lesson['teacher']}\n"
            text += f"🚪 Ауд.: {lesson['room']}\n"
            
        return text
        
    @staticmethod
    def format_week_schedule(schedules: List[Dict[str, any]]) -> List[str]:
        """
        Форматирование расписания на неделю
        Возвращает список сообщений (по одному на день)
        
        Args:
            schedules: Список расписаний по дням
            
        Returns:
            Список отформатированных строк
        """
        messages = []
        
        for schedule in schedules:
            if schedule["lessons"]:
                msg = ScheduleFormatter.format_day_schedule(schedule)
                messages.append(msg)
                
        if not messages:
            return ["🎉 На этой неделе занятий нет!"]
            
        return messages
        
    @staticmethod
    def format_short_day(schedule: Dict[str, any]) -> str:
        """
        Краткое форматирование дня (для списка)
        
        Args:
            schedule: Словарь с расписанием
            
        Returns:
            Краткая строка
        """
        lessons_count = len(schedule.get("lessons", []))
        
        if lessons_count == 0:
            return f"📅 {schedule['date']} ({schedule['day_of_week'][:2]}) - нет занятий"
        
        return f"📅 {schedule['date']} ({schedule['day_of_week'][:2]}) - {lessons_count} пар"
        
    @staticmethod
    def format_next_lesson(schedule: Dict[str, any]) -> str:
        """
        Форматирование ближайшего занятия
        
        Args:
            schedule: Словарь с расписанием
            
        Returns:
            Отформатированная строка
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        if not schedule.get("lessons"):
            return "Сегодня занятий больше нет! 🎉"
            
        for lesson in schedule["lessons"]:
            lesson_end = lesson["time"].split(" - ")[1]
            if current_time < lesson_end:
                return (
                    f"⏰ <b>Следующее занятие:</b>\n\n"
                    f"🔢 {lesson['number']} пара ({lesson['time']})\n"
                    f"📚 {lesson['name']}\n"
                    f"📝 {lesson['type']}\n"
                    f"👨‍🏫 {lesson['teacher']}\n"
                    f"🚪 {lesson['room']}"
                )
                
        return "Сегодня занятий больше нет! 🎉"
        
    @staticmethod
    def format_group_info(group: Dict[str, str]) -> str:
        """
        Форматирование информации о группе
        
        Args:
            group: Словарь с информацией о группе
            
        Returns:
            Отформатированная строка
        """
        return f"👥 <b>{group['name']}</b>\n{group.get('full_name', '')}"

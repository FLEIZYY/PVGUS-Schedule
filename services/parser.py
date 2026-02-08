"""Парсер расписания с сайта ПВГУС"""
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json

from utils.logger import logger
from config import settings


class ScheduleParser:
    """Парсер расписания"""
    
    def __init__(self):
        self.base_url = "https://lk.tolgas.ru/public-schedule/group"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Создание сессии"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def fetch_schedule_html(
        self,
        group_name: str,
        date_from: datetime,
        date_to: datetime
    ) -> str:
        """
        Получение HTML расписания с сайта
        
        Args:
            group_name: Название группы
            date_from: Начальная дата
            date_to: Конечная дата
            
        Returns:
            HTML код страницы
        """
        params = {
            "id": group_name,
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d")
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                response.raise_for_status()
                html = await response.text()
                logger.info(f"Получен HTML для группы {group_name}")
                return html
        except Exception as e:
            logger.error(f"Ошибка получения HTML: {e}")
            raise
    
    def parse_schedule_html(self, html: str) -> List[Dict[str, str]]:
        """
        Парсинг HTML расписания
        
        Args:
            html: HTML код страницы
            
        Returns:
            Список занятий
        """
        soup = BeautifulSoup(html, "lxml")
        
        schedule = []
        current_date = None
        
        for block in soup.select("div.date-bar, div.lesson-item"):
            
            # Если это дата — обновляем текущую
            if "date-bar" in block.get("class", []):
                date_span = block.find("span")
                if date_span:
                    current_date = date_span.text.strip()
            
            # Если это пара — парсим и добавляем с датой
            elif "lesson-item" in block.get("class", []):
                try:
                    number_div = block.find("div", class_="lesson-number")
                    number = number_div.contents[0].strip() if number_div else ""
                    
                    time_div = block.find("div", class_="lesson-time")
                    time = time_div.text.strip() if time_div else ""
                    
                    title_div = block.find("div", class_="lesson-title")
                    name = title_div.text.strip() if title_div else ""
                    
                    room_tag = block.find("span", class_="lesson-auditorium")
                    room = room_tag.text.strip() if room_tag else ""
                    
                    type_div = block.find("div", class_="lesson-type")
                    type_ = type_div.text.strip() if type_div else ""
                    
                    # Поиск преподавателя
                    teacher = ""
                    details_div = block.find("div", class_="lesson-details")
                    if details_div:
                        details = details_div.get_text("\n")
                        for line in details.split("\n"):
                            if "Преподаватель:" in line:
                                teacher = line.replace("Преподаватель:", "").strip()
                                break
                    
                    schedule.append({
                        "date": current_date,
                        "number": number,
                        "time": time,
                        "name": name,
                        "type": type_,
                        "teacher": teacher,
                        "room": room
                    })
                    
                except Exception as e:
                    logger.error(f"Ошибка парсинга занятия: {e}")
                    continue
        
        return schedule
            
    async def search_groups(self, query: str = "") -> List[Dict[str, str]]:
        """
        Поиск групп
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список групп с информацией
        """
        try:
            # Список известных групп (можно расширить или парсить с сайта)
            groups = [
                {"id": "БОЗИ24", "name": "БОЗИ24", "full_name": "БОЗИ24 - Информационная безопасность"},
                {"id": "БОЗИЗ24", "name": "БОЗИЗ24", "full_name": "БОЗИЗ24 - Информационная безопасность (заочная)"},
                {"id": "ПИ-101", "name": "ПИ-101", "full_name": "ПИ-101 - Прикладная информатика"},
                {"id": "ИС-201", "name": "ИС-201", "full_name": "ИС-201 - Информационные системы"},
            ]
            
            if query:
                groups = [g for g in groups if query.upper() in g["name"].upper()]
                
            logger.info(f"Найдено групп: {len(groups)}")
            return groups
            
        except Exception as e:
            logger.error(f"Ошибка поиска групп: {e}")
            return []
            
    async def get_schedule(
        self, 
        group_name: str, 
        date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Получение расписания для группы на определенную дату
        
        Args:
            group_name: Название группы
            date: Дата (по умолчанию - сегодня)
            
        Returns:
            Словарь с расписанием
        """
        if date is None:
            date = datetime.now()
            
        try:
            # Получаем расписание на этот день (с небольшим запасом)
            date_from = date
            date_to = date
            
            html = await self.fetch_schedule_html(group_name, date_from, date_to)
            all_lessons = self.parse_schedule_html(html)
            
            # Фильтруем занятия для нужной даты
            target_date_str = date.strftime("%d.%m.%Y")
            day_lessons = []
            
            for lesson in all_lessons:
                lesson_date = lesson.get("date", "")
                # Преобразуем дату из формата "07.02.26 Суббота" в "07.02.2026"
                if lesson_date:
                    try:
                        # Извлекаем дату без дня недели
                        date_part = lesson_date.split()[0]  # "07.02.26"
                        # Преобразуем в полный год
                        day, month, year = date_part.split(".")
                        if len(year) == 2:
                            year = "20" + year
                        lesson_date_formatted = f"{day}.{month}.{year}"
                        
                        if lesson_date_formatted == target_date_str:
                            day_lessons.append({
                                "number": int(lesson["number"]) if lesson["number"].isdigit() else 0,
                                "time": lesson["time"],
                                "name": lesson["name"],
                                "type": lesson["type"],
                                "teacher": lesson["teacher"],
                                "room": lesson["room"]
                            })
                    except Exception as e:
                        logger.error(f"Ошибка обработки даты {lesson_date}: {e}")
            
            logger.info(f"Получено расписание для {group_name} на {target_date_str}: {len(day_lessons)} занятий")
            
            return {
                "date": target_date_str,
                "day_of_week": self._get_day_name(date.weekday()),
                "group_name": group_name,
                "lessons": sorted(day_lessons, key=lambda x: x["number"])
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            return {
                "date": date.strftime("%d.%m.%Y"),
                "day_of_week": self._get_day_name(date.weekday()),
                "group_name": group_name,
                "lessons": []
            }
            
    async def get_week_schedule(
        self, 
        group_name: str,
        start_date: Optional[datetime] = None
    ) -> List[Dict[str, any]]:
        """
        Получение расписания на неделю
        
        Args:
            group_name: Название группы
            start_date: Начальная дата (по умолчанию - понедельник текущей недели)
            
        Returns:
            Список расписаний по дням
        """
        if start_date is None:
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
        
        end_date = start_date + timedelta(days=6)
        
        try:
            # Получаем расписание на всю неделю одним запросом
            html = await self.fetch_schedule_html(group_name, start_date, end_date)
            all_lessons = self.parse_schedule_html(html)
            
            # Группируем по дням
            week_schedule = []
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                target_date_str = current_date.strftime("%d.%m.%Y")
                
                day_lessons = []
                for lesson in all_lessons:
                    lesson_date = lesson.get("date", "")
                    if lesson_date:
                        try:
                            date_part = lesson_date.split()[0]
                            day, month, year = date_part.split(".")
                            if len(year) == 2:
                                year = "20" + year
                            lesson_date_formatted = f"{day}.{month}.{year}"
                            
                            if lesson_date_formatted == target_date_str:
                                day_lessons.append({
                                    "number": int(lesson["number"]) if lesson["number"].isdigit() else 0,
                                    "time": lesson["time"],
                                    "name": lesson["name"],
                                    "type": lesson["type"],
                                    "teacher": lesson["teacher"],
                                    "room": lesson["room"]
                                })
                        except Exception as e:
                            logger.error(f"Ошибка обработки даты: {e}")
                
                week_schedule.append({
                    "date": target_date_str,
                    "day_of_week": self._get_day_name(current_date.weekday()),
                    "group_name": group_name,
                    "lessons": sorted(day_lessons, key=lambda x: x["number"])
                })
            
            return week_schedule
            
        except Exception as e:
            logger.error(f"Ошибка получения недельного расписания: {e}")
            # Возвращаем пустое расписание на неделю
            week_schedule = []
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                week_schedule.append({
                    "date": current_date.strftime("%d.%m.%Y"),
                    "day_of_week": self._get_day_name(current_date.weekday()),
                    "group_name": group_name,
                    "lessons": []
                })
            return week_schedule
        
    def _get_day_name(self, weekday: int) -> str:
        """Получение названия дня недели"""
        days = [
            "Понедельник",
            "Вторник", 
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье"
        ]
        return days[weekday]


# Создаем глобальный экземпляр парсера
async def create_parser() -> ScheduleParser:
    """Создание парсера"""
    return ScheduleParser()

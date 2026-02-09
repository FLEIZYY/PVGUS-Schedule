"""Парсер расписания с сайта ПВГУС"""
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
import json
import asyncio

from utils.logger import logger

class ScheduleParser:
    """Парсер расписания"""
    
    def __init__(self):
        self.base_url = "https://lk.tolgas.ru/public-schedule/group"
        # Страница поиска, где лежит JS массив с группами
        self.search_url = "https://lk.tolgas.ru/public-schedule/search" 
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://lk.tolgas.ru/public-schedule/",
            "X-Requested-With": "XMLHttpRequest"
        }
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_groups(self, query: str = "") -> List[Dict[str, str]]:
        """
        Парсит группы из JS-массива на странице поиска.
        Ищет массив строк, ПРОПУСКАЯ массив чисел.
        """
        try:
            # Загружаем страницу поиска
            async with self.session.get(self.search_url) as response:
                if response.status != 200:
                    logger.error(f"Ошибка доступа к поиску: {response.status}")
                    return []
                
                html = await response.text()
                
                # Ищем ВСЕ вхождения "const groups = [...]"
                # Используем findall, чтобы найти и мусорный массив, и настоящий
                pattern = r'const\s+groups\s*=\s*(\[.*?\]);'
                matches = re.findall(pattern, html, re.DOTALL)
                
                all_groups = []
                found_correct_array = False

                for json_str in matches:
                    # --- ГЛАВНАЯ ПРОВЕРКА ---
                    # Если в массиве нет кавычек, это массив чисел [0,1,2...] -> пропускаем
                    if '"' not in json_str and "'" not in json_str:
                        continue
                        
                    try:
                        # Парсим найденную строку как JSON
                        raw_list = json.loads(json_str)
                        
                        # Дополнительная проверка: первый элемент должен быть строкой
                        if raw_list and isinstance(raw_list[0], str):
                            # Ура, это тот самый массив! Преобразуем в словарей
                            for name in raw_list:
                                all_groups.append({
                                    "id": name,
                                    "name": name,
                                    "full_name": name
                                })
                            found_correct_array = True
                            # logger.info(f"Успешно загружен массив из {len(all_groups)} групп")
                            break # Выходим из цикла, мы нашли то что нужно
                            
                    except json.JSONDecodeError:
                        continue
                
                if not found_correct_array:
                    logger.warning("Не удалось найти правильный массив групп в JS")
                    return []

                # Фильтрация по запросу пользователя
                if query:
                    query = query.upper().strip()
                    filtered = [g for g in all_groups if query in g["name"].upper()]
                    logger.info(f"Найдено групп по запросу '{query}': {len(filtered)}")
                    return filtered
                
                # Если запроса нет, возвращаем первые 50 (чтобы список не был пустым при открытии меню)
                # или возвращаем пустой список, если хотите заставить пользователя вводить поиск
                return all_groups[:50] 
                
        except Exception as e:
            logger.error(f"Критическая ошибка поиска: {e}")
            return []
    
    async def fetch_schedule_html(self, group_name: str, date_from: datetime, date_to: datetime) -> str:
        """Получение HTML расписания с датами"""
        params = {
            "id": group_name,
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d")
        }
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logger.error(f"Ошибка получения HTML: {e}")
            raise
    
    def parse_schedule_html(self, html: str) -> List[Dict[str, str]]:
        """Парсинг HTML страницы"""
        soup = BeautifulSoup(html, "lxml")
        schedule = []
        current_date = None
        
        for block in soup.select("div.date-bar, div.lesson-item"):
            # Если блок - это дата
            if "date-bar" in block.get("class", []):
                date_span = block.find("span")
                if date_span:
                    current_date = date_span.text.strip()
            
            # Если блок - это пара
            elif "lesson-item" in block.get("class", []):
                try:
                    number_div = block.find("div", class_="lesson-number")
                    # .contents[0] берет только текст номера пары, игнорируя время внутри div
                    number = number_div.contents[0].strip() if number_div else "0"
                    
                    time_div = block.find("div", class_="lesson-time")
                    time = time_div.text.strip() if time_div else ""
                    
                    title_div = block.find("div", class_="lesson-title")
                    name = title_div.text.strip() if title_div else ""
                    
                    room_tag = block.find("span", class_="lesson-auditorium")
                    room = room_tag.text.strip() if room_tag else ""
                    
                    type_div = block.find("div", class_="lesson-type")
                    type_ = type_div.text.strip() if type_div else ""
                    
                    teacher = ""
                    details_div = block.find("div", class_="lesson-details")
                    if details_div:
                        details_text = details_div.get_text("\n")
                        for line in details_text.split("\n"):
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

    # --- Метод для произвольного диапазона ---
    async def get_custom_schedule(self, group_name: str, date_start: datetime, date_end: datetime) -> List[Dict[str, any]]:
        try:
            html = await self.fetch_schedule_html(group_name, date_start, date_end)
            all_lessons = self.parse_schedule_html(html)
            
            schedule_map = {}
            for lesson in all_lessons:
                date_key = lesson['date']
                if not date_key: continue
                
                if date_key not in schedule_map:
                    schedule_map[date_key] = {
                        "date": date_key,
                        "day_of_week": "", # День недели можно вычислить отдельно или оставить пустым
                        "group_name": group_name,
                        "lessons": []
                    }
                
                schedule_map[date_key]["lessons"].append({
                    "number": int(lesson["number"]) if lesson["number"].isdigit() else 0,
                    "time": lesson["time"],
                    "name": lesson["name"],
                    "type": lesson["type"],
                    "teacher": lesson["teacher"],
                    "room": lesson["room"]
                })
            
            return list(schedule_map.values())
        except Exception as e:
            logger.error(f"Ошибка custom schedule: {e}")
            return []

    # --- Обертки для совместимости ---
    async def get_schedule(self, group_name: str, date: Optional[datetime] = None) -> Dict[str, any]:
        if date is None: date = datetime.now()
        res = await self.get_custom_schedule(group_name, date, date)
        return res[0] if res else {"date": date.strftime("%d.%m.%Y"), "lessons": [], "day_of_week": "", "group_name": group_name}

    async def get_week_schedule(self, group_name: str, start_date: Optional[datetime] = None) -> List[Dict[str, any]]:
        if start_date is None:
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        return await self.get_custom_schedule(group_name, start_date, end_date)

    def _get_day_name(self, weekday: int) -> str:
        return ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][weekday]

async def create_parser() -> ScheduleParser:
    return ScheduleParser()
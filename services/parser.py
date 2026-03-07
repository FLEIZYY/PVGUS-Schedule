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
    
    async def search_targets(self, query: str = "", role: str = "student") -> List[Dict[str, str]]:
        """Парсит группы или преподавателей в зависимости от роли."""
        try:
            async with self.session.get(self.search_url) as response:
                if response.status != 200: return []
                html = await response.text()
                
                # Ищем массив groups или teachers
                target_var = "groups" if role == "student" else "teachers"
                pattern = rf'const\s+{target_var}\s*=\s*(\[.*?\]);'
                matches = re.findall(pattern, html, re.DOTALL)
                
                all_targets = []
                for json_str in matches:
                    if '"' not in json_str and "'" not in json_str: continue
                    try:
                        raw_list = json.loads(json_str)
                        if raw_list and isinstance(raw_list[0], str):
                            for name in raw_list:
                                all_targets.append({"id": name, "name": name, "full_name": name})
                            break
                    except json.JSONDecodeError:
                        continue

                if query:
                    query = query.upper().strip()
                    return [g for g in all_targets if query in g["name"].upper()]
                
                return all_targets[:50] 
                
        except Exception as e:
            logger.error(f"Критическая ошибка поиска: {e}")
            return []
    
    async def fetch_schedule_html(self, target_name: str, date_from: datetime, date_to: datetime, role: str = "student") -> str:
        """Получение HTML расписания с датами для нужной роли"""
        endpoint = "teacher" if role == "teacher" else "group"
        url = f"https://lk.tolgas.ru/public-schedule/{endpoint}"
        
        if role == "teacher":
            # Для преподавателей сайт требует другие названия параметров!
            params = {
                "name": target_name,
                "date": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d")
            }
        else:
            # Для студентов
            params = {
                "id": target_name,
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d")
            }
                
        try:
            async with self.session.get(url, params=params) as response:
                html = await response.text()
                return html
        except Exception as e:
            logger.error(f"❌ [ПАРСЕР] Ошибка HTTP запроса: {e}")
            raise
    
    def parse_schedule_html(self, html: str) -> List[Dict[str, str]]:
        """Парсинг HTML страницы"""
        soup = BeautifulSoup(html, "lxml")
        schedule = []
        current_date = None
        lessons_found = 0
        
        for block in soup.select("div.date-bar, div.lesson-item"):
            if "date-bar" in block.get("class", []):
                date_span = block.find("span")
                if date_span: current_date = date_span.text.strip()
            
            elif "lesson-item" in block.get("class", []):
                lessons_found += 1
                try:
                    number_div = block.find("div", class_="lesson-number")
                    number = number_div.contents[0].strip() if number_div else "0"
                    
                    time_div = block.find("div", class_="lesson-time")
                    time = time_div.text.strip() if time_div else ""
                    
                    title_div = block.find("div", class_="lesson-title")
                    name = title_div.text.strip() if title_div else ""
                    
                    room_tag = block.find("span", class_="lesson-auditorium")
                    room = room_tag.text.strip() if room_tag else ""
                    
                    type_div = block.find("div", class_="lesson-type")
                    type_ = type_div.text.strip() if type_div else ""
                    
                    teacher_or_group = ""
                    details_div = block.find("div", class_="lesson-details")
                    if details_div:
                        # 1. Вариант для студентов (ищем слово "Преподаватель:")
                        details_text = details_div.get_text("\n")
                        for line in details_text.split("\n"):
                            if "Преподаватель:" in line:
                                teacher_or_group = line.replace("Преподаватель:", "").strip()
                                break
                                
                        # 2. Вариант для преподавателей (ищем иконку фа-users)
                        if not teacher_or_group:
                            users_icon = details_div.find("i", class_="fa-users")
                            if users_icon:
                                # Текст группы идет сразу после иконки
                                next_node = users_icon.next_sibling
                                if next_node and isinstance(next_node, str):
                                    # Убираем пробелы и возможные кавычки
                                    teacher_or_group = next_node.strip().replace('"', '')
                    
                    schedule.append({
                        "date": current_date,
                        "number": number,
                        "time": time,
                        "name": name,
                        "type": type_,
                        "teacher": teacher_or_group, # Теперь здесь будет "БОЗИ24"
                        "room": room
                    })
                except Exception as e:
                    logger.error(f"⚠️ Ошибка парсинга одной пары: {e}")
                    continue
                    
        return schedule

    async def get_custom_schedule(self, target_name: str, date_start: datetime, date_end: datetime, role: str = "student") -> List[Dict[str, any]]:
        try:
            html = await self.fetch_schedule_html(target_name, date_start, date_end, role)
            all_lessons = self.parse_schedule_html(html)
            
            schedule_map = {}
            for lesson in all_lessons:
                date_key = lesson['date']
                if not date_key: continue
                
                if date_key not in schedule_map:
                    schedule_map[date_key] = {
                        "date": date_key,
                        "day_of_week": "",
                        "group_name": target_name,
                        "role": role,  # Добавляем роль в словарь для картинки!
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

    async def get_schedule(self, target_name: str, date: Optional[datetime] = None, role: str = "student") -> Dict[str, any]:
        if date is None: date = datetime.now()
        res = await self.get_custom_schedule(target_name, date, date, role)
        return res[0] if res else {"date": date.strftime("%d.%m.%Y"), "lessons": [], "day_of_week": "", "group_name": target_name, "role": role}

    async def get_week_schedule(self, target_name: str, start_date: Optional[datetime] = None, role: str = "student") -> List[Dict[str, any]]:
        if start_date is None:
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        return await self.get_custom_schedule(target_name, start_date, end_date, role)

    def _get_day_name(self, weekday: int) -> str:
        return ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][weekday]

async def create_parser() -> ScheduleParser:
    return ScheduleParser()
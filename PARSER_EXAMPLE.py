"""
ПРИМЕР РЕАЛЬНОГО ПАРСЕРА РАСПИСАНИЯ

Этот файл показывает, как можно реализовать реальный парсинг сайта.
Замените функции в services/parser.py на эти, адаптировав под структуру сайта.

ВАЖНО: Сначала нужно изучить структуру сайта https://lk.tolgas.ru/public-schedule/search/
и найти API endpoints или HTML структуру для парсинга.
"""

import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import json


async def real_search_groups(session: aiohttp.ClientSession, query: str = "") -> List[Dict[str, str]]:
    """
    Реальный поиск групп на сайте
    
    Пример с использованием API (если есть):
    """
    url = "https://lk.tolgas.ru/api/groups"  # Примерный URL
    
    try:
        async with session.get(url, params={"search": query}) as response:
            if response.status == 200:
                data = await response.json()
                return [
                    {
                        "id": str(group["id"]),
                        "name": group["name"],
                        "full_name": group.get("full_name", group["name"])
                    }
                    for group in data.get("groups", [])
                ]
    except Exception as e:
        print(f"Ошибка поиска групп: {e}")
    
    return []


async def real_get_schedule_html(
    session: aiohttp.ClientSession,
    group_name: str,
    date: datetime
) -> Dict[str, any]:
    """
    Парсинг расписания из HTML
    
    Этот метод нужно использовать, если на сайте нет API
    """
    url = f"https://lk.tolgas.ru/public-schedule/group/{group_name}"
    params = {
        "date": date.strftime("%Y-%m-%d")
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return {"lessons": []}
            
            html = await response.text()
            soup = BeautifulSoup(html, "lxml")
            
            lessons = []
            
            # Пример парсинга (структура зависит от реального HTML)
            schedule_items = soup.find_all("div", class_="schedule-item")
            
            for item in schedule_items:
                try:
                    lesson = {
                        "number": int(item.find("span", class_="lesson-number").text.strip()),
                        "time": item.find("span", class_="lesson-time").text.strip(),
                        "name": item.find("div", class_="lesson-name").text.strip(),
                        "type": item.find("span", class_="lesson-type").text.strip(),
                        "teacher": item.find("div", class_="teacher-name").text.strip(),
                        "room": item.find("span", class_="room-number").text.strip()
                    }
                    lessons.append(lesson)
                except (AttributeError, ValueError) as e:
                    print(f"Ошибка парсинга занятия: {e}")
                    continue
            
            return {
                "date": date.strftime("%d.%m.%Y"),
                "day_of_week": get_day_name(date.weekday()),
                "group_name": group_name,
                "lessons": lessons
            }
            
    except Exception as e:
        print(f"Ошибка получения расписания: {e}")
        return {"lessons": []}


async def real_get_schedule_api(
    session: aiohttp.ClientSession,
    group_name: str,
    date: datetime
) -> Dict[str, any]:
    """
    Получение расписания через API (если есть)
    
    Более предпочтительный метод, если сайт предоставляет API
    """
    url = "https://lk.tolgas.ru/api/schedule"  # Примерный URL
    params = {
        "group": group_name,
        "date": date.strftime("%Y-%m-%d")
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                
                # Преобразуем формат API в наш формат
                lessons = [
                    {
                        "number": lesson["number"],
                        "time": lesson["time"],
                        "name": lesson["subject"],
                        "type": lesson["type"],
                        "teacher": lesson["teacher"],
                        "room": lesson["room"]
                    }
                    for lesson in data.get("lessons", [])
                ]
                
                return {
                    "date": date.strftime("%d.%m.%Y"),
                    "day_of_week": get_day_name(date.weekday()),
                    "group_name": group_name,
                    "lessons": lessons
                }
    except Exception as e:
        print(f"Ошибка API: {e}")
    
    return {"lessons": []}


def get_day_name(weekday: int) -> str:
    """Получение названия дня недели"""
    days = [
        "Понедельник", "Вторник", "Среда", "Четверг",
        "Пятница", "Суббота", "Воскресенье"
    ]
    return days[weekday]


"""
ИНСТРУКЦИЯ ПО ИНТЕГРАЦИИ:

1. Откройте сайт https://lk.tolgas.ru/public-schedule/search/ в браузере
2. Откройте DevTools (F12) и перейдите на вкладку Network
3. Выполните поиск группы и посмотрите, какие запросы отправляются
4. Найдите:
   - Endpoint для поиска групп
   - Endpoint для получения расписания
   - Формат данных (JSON или HTML)

5. Если есть API:
   - Используйте функцию real_get_schedule_api()
   - Адаптируйте URL и параметры под реальный API

6. Если только HTML:
   - Используйте функцию real_get_schedule_html()
   - Изучите HTML структуру страницы
   - Найдите CSS классы элементов расписания
   - Адаптируйте селекторы в BeautifulSoup

7. Замените функции в services/parser.py:
   - search_groups() -> используйте real_search_groups()
   - get_schedule() -> используйте real_get_schedule_api() или real_get_schedule_html()

ПРИМЕР ИССЛЕДОВАНИЯ САЙТА:

# В браузере откройте консоль и выполните:
fetch('https://lk.tolgas.ru/api/groups')
  .then(r => r.json())
  .then(console.log)

# Если получите данные - есть API!
# Если 404 или ошибка - нужно парсить HTML

ДЛЯ HTML ПАРСИНГА:

1. Найдите элемент с расписанием:
   - Правый клик -> Inspect Element
   - Найдите родительский контейнер
   - Запишите его класс или ID

2. Найдите элементы занятий:
   - Каждое занятие обычно в отдельном div
   - Запишите селекторы для:
     * Номер пары
     * Время
     * Название предмета
     * Тип занятия (лекция/практика)
     * Преподаватель
     * Аудитория

3. Используйте эти селекторы в BeautifulSoup

ПРИМЕР РАБОТЫ С РАЗНЫМИ ФОРМАТАМИ:

# Если данные приходят в формате:
{
  "success": true,
  "data": {
    "schedule": [
      {"lessonNumber": 1, "subject": "Математика", ...}
    ]
  }
}

# Адаптируйте так:
data = await response.json()
if data.get("success"):
    raw_lessons = data["data"]["schedule"]
    lessons = [transform_lesson(l) for l in raw_lessons]
"""

"""Генератор изображений расписания"""
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any
from io import BytesIO
import os
import re


class ScheduleImageGenerator:
    """Генерация изображений расписания"""
    
    # Цветовая схема
    COLORS = {
        'background': '#1a1a2e',
        'card_bg': '#16213e',
        'header': '#0f3460',
        'text_primary': '#ffffff',
        'text_secondary': '#94a3b8',
        'accent': '#e94560',
        'border': '#533483',
        'watermark': 'rgba(233, 69, 96, 0.15)'
    }
    
    # Размеры
    WIDTH = 1080
    PADDING = 40
    CARD_PADDING = 30
    
    def __init__(self):
        """Инициализация генератора"""
        self.fonts = self._load_fonts()
    
    def _load_fonts(self) -> Dict:
        """Загрузка шрифтов с резервными вариантами"""
        fonts = {}
        font_paths = ["benzin-bold.ttf"]
        
        try:
            for path in font_paths:
                if os.path.exists(path):
                    fonts['header']   = ImageFont.truetype(path, 48)
                    fonts['title']    = ImageFont.truetype(path, 36)
                    fonts['subtitle'] = ImageFont.truetype(path, 28)
                    fonts['text']     = ImageFont.truetype(path, 24)
                    fonts['small']    = ImageFont.truetype(path, 20)
                    fonts['watermark']= ImageFont.truetype(path, 80)
                    break
            
            if not fonts:
                raise Exception("Font not found")
                
        except Exception:
            fonts['header']   = ImageFont.load_default()
            fonts['title']    = ImageFont.load_default()
            fonts['subtitle'] = ImageFont.load_default()
            fonts['text']     = ImageFont.load_default()
            fonts['small']    = ImageFont.load_default()
            fonts['watermark']= ImageFont.load_default()
        
        return fonts
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _parse_rgba(self, rgba_str: str) -> tuple:
        if rgba_str.startswith('rgba'):
            values = rgba_str.replace('rgba(', '').replace(')', '').split(',')
            return tuple(int(float(v.strip()) * 255) if i == 3 else int(v.strip()) 
                         for i, v in enumerate(values))
        return self._hex_to_rgb(rgba_str)
    
    def _clean_text(self, text: Any) -> str:
        """Удаляет рамочные символы и лишние пробелы"""
        if not isinstance(text, str):
            return str(text)
        
        # Удаляем box-drawing символы и похожие
        text = re.sub(r'[\u2500-\u257F\u2500-\u25FF╔╗╚╝═║╠╣╟╢│├└┌┐┘]', '', text)
        text = re.sub(r'\s+', ' ', text)  # нормализация пробелов
        return text.strip()
    
    def _draw_rounded_rectangle(self, draw: ImageDraw, coords: tuple, 
                               radius: int, fill: str, outline: str = None):
        x1, y1, x2, y2 = coords
        
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
        
        if outline:
            draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=2)
            draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=2)
            draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=2)
            draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=2)
            draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=2)
            draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=2)
            draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=2)
            draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=2)
    
    def _get_lesson_emoji(self, lesson_type: str) -> str:
        # Возвращаем пустую строку, чтобы убрать эмодзи типов занятий (📖, 💻 и т.д.)
        return ""
    
    def generate_schedule_image(self, schedule: Dict) -> BytesIO:
        lessons = schedule.get('lessons', [])
        
        header_height = 200
        lesson_height = 180
        footer_height = 100
        
        total_height = header_height + (len(lessons) * lesson_height if lessons else 150) + footer_height
        
        img = Image.new('RGB', (self.WIDTH, total_height), self._hex_to_rgb(self.COLORS['background']))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        y_offset = self.PADDING
        
        # Шапка
        self._draw_header(draw, schedule, y_offset)
        y_offset += header_height
        
        # Занятия или сообщение об отсутствии
        if lessons:
            for lesson in lessons:
                self._draw_lesson_card(draw, lesson, y_offset)
                y_offset += lesson_height
        else:
            self._draw_no_lessons(draw, y_offset)
            y_offset += 150
        
        # Футер
        self._draw_footer(draw, total_height - footer_height)
        
        output = BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)
        
        return output
    
    def _draw_header(self, draw: ImageDraw, schedule: Dict, y: int):
        header_bg = self._hex_to_rgb(self.COLORS['header'])
        draw.rectangle([self.PADDING, y, self.WIDTH - self.PADDING, y + 160], fill=header_bg)
        
        date_text = self._clean_text(schedule.get('date', 'Дата не указана'))
        draw.text((self.WIDTH // 2, y + 40), date_text, font=self.fonts['title'], fill=self._hex_to_rgb(self.COLORS['text_primary']), anchor='mm')
        
        day_text = self._clean_text(schedule.get('day_of_week', ''))
        draw.text((self.WIDTH // 2, y + 80), day_text, font=self.fonts['subtitle'], fill=self._hex_to_rgb(self.COLORS['text_secondary']), anchor='mm')
        
        # ДИНАМИЧЕСКИЙ ТЕКСТ (зависит от переданной роли)
        role = schedule.get('role', 'student')
        prefix = "Группа:" if role == "student" else "Преподаватель:"
        
        group_text = f"{prefix} {self._clean_text(schedule.get('group_name', 'Не указана'))}"
        draw.text((self.WIDTH // 2, y + 120), group_text, font=self.fonts['text'], fill=self._hex_to_rgb(self.COLORS['accent']), anchor='mm')    
    def _draw_lesson_card(self, draw: ImageDraw, lesson: Dict, y: int):
        lesson_clean = {k: self._clean_text(v) for k, v in lesson.items()}
        
        card_x1 = self.PADDING + 20
        card_y1 = y + 10
        card_x2 = self.WIDTH - self.PADDING - 20
        card_y2 = y + 170
        
        self._draw_rounded_rectangle(
            draw,
            (card_x1, card_y1, card_x2, card_y2),
            radius=15,
            fill=self._hex_to_rgb(self.COLORS['card_bg']),
            outline=self._hex_to_rgb(self.COLORS['border'])
        )
        
        x = card_x1 + self.CARD_PADDING
        y_text = card_y1 + 20
        
        # Убрали переменную {emoji} в начале строки
        header = f"{lesson_clean.get('number', '')} пара • {lesson_clean.get('time', '')}"
        draw.text(
            (x, y_text),
            header,
            font=self.fonts['subtitle'],
            fill=self._hex_to_rgb(self.COLORS['accent'])
        )
        
        y_text += 40
        draw.text(
            (x, y_text),
            lesson_clean.get('name', 'Предмет не указан')[:50],
            font=self.fonts['text'],
            fill=self._hex_to_rgb(self.COLORS['text_primary'])
        )
        
        y_text += 35
        # Убрали "📝 " и "👨‍🏫 "
        details = f"{lesson_clean.get('type', '')} • {lesson_clean.get('teacher', '')}"
        draw.text(
            (x, y_text),
            details[:60],
            font=self.fonts['small'],
            fill=self._hex_to_rgb(self.COLORS['text_secondary'])
        )
        
        y_text += 30
        # Убрали "🚪 "
        room = f"Аудитория: {lesson_clean.get('room', 'Не указана')}"
        draw.text(
            (x, y_text),
            room,
            font=self.fonts['small'],
            fill=self._hex_to_rgb(self.COLORS['text_secondary'])
        )
    
    def _draw_no_lessons(self, draw: ImageDraw, y: int):
        text = "РАСПИСАНИЕ ОТСУТСТВУЕТ"
        draw.text(
            (self.WIDTH // 2, y + 50),
            text,
            font=self.fonts['title'],
            fill=self._hex_to_rgb(self.COLORS['accent']),
            anchor='mm'
        )
        
        subtext = "Занятий в этот день нет!"
        draw.text(
            (self.WIDTH // 2, y + 110),
            subtext,
            font=self.fonts['text'],
            fill=self._hex_to_rgb(self.COLORS['text_secondary']),
            anchor='mm'
        )
    
    def _draw_footer(self, draw: ImageDraw, y: int):
        line_y = y + 20
        draw.line(
            [self.PADDING + 40, line_y, self.WIDTH - self.PADDING - 40, line_y],
            fill=self._hex_to_rgb(self.COLORS['border']),
            width=2
        )
        
        text_y = y + 65
        
        # Слева — FLEIZY
        # Используем координату начала (PADDING) и якорь 'lm' (Left Middle)
        draw.text(
            (self.PADDING + 50, text_y),
            "FLEIZY",
            font=self.fonts['text'],
            fill=self._hex_to_rgb(self.COLORS['accent']),
            anchor='lm'   # left middle
        )
        
        # Справа — @delovoybalik
        # Используем координату конца (WIDTH) и якорь 'rm' (Right Middle)
        draw.text(
            (self.WIDTH - self.PADDING - 50, text_y),
            "@delovoybalik",
            font=self.fonts['text'],
            fill=self._hex_to_rgb(self.COLORS['accent']),
            anchor='rm'   # right middle
        )
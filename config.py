# config.py
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Основные настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CODE = os.getenv("ADMIN_CODE", "admin123")
TEACHER_CODE = os.getenv("TEACHER_CODE", "teacher123")
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/school.db")

# Импорт локализации
from localization.kz_text import ROLES, STATUSES, WEEKDAYS, SUBJECTS

# Настройки модуля посещаемости
QR_CODE_VALIDITY_MINUTES = 10

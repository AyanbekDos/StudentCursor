import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Основные настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CODE = os.getenv("ADMIN_CODE", "admin123")
TEACHER_CODE = os.getenv("TEACHER_CODE", "teacher123")
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/school.db")

# Роли пользователей
ROLES = {
    "student": "Студент",
    "teacher": "Преподаватель",
    "admin": "Администратор"
}

# Статусы пользователей
STATUSES = {
    "pending": "Ожидает подтверждения",
    "approved": "Подтвержден",
    "rejected": "Отклонен"
}

# Дни недели
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Предметы
SUBJECTS = [
    "Математика", 
    "Физика", 
    "Информатика", 
    "История", 
    "Английский язык"
] 

# Настройки модуля посещаемости
QR_CODE_VALIDITY_MINUTES = 10
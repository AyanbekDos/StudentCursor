from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_student_keyboard():
    """
    Создает клавиатуру для студента
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками для студента
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📊 Расписание"), KeyboardButton("📝 Оценки"))
    keyboard.add(KeyboardButton("🔔 Уведомления"), KeyboardButton("📸 Отметиться"))
    return keyboard

def get_teacher_keyboard():
    """
    Создает клавиатуру для преподавателя
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками для преподавателя
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📊 Расписание"), KeyboardButton("📝 Выставить оценки"))
    keyboard.add(KeyboardButton("🔔 Уведомления"), KeyboardButton("📋 Заявки"))
    keyboard.add(KeyboardButton("👥 Управление группами"), KeyboardButton("🔄 Создать QR-код"))
    return keyboard

def get_admin_keyboard():
    """
    Создает клавиатуру для администратора
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками для администратора
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📊 Расписание"), KeyboardButton("📝 Выставить оценки"))
    keyboard.add(KeyboardButton("🔔 Уведомления"), KeyboardButton("📋 Заявки"))
    keyboard.add(KeyboardButton("👥 Управление группами"), KeyboardButton("🔄 Создать QR-код"))
    keyboard.add(KeyboardButton("⚙️ Настройки системы"))
    return keyboard

# Словарь соответствия текстовых команд и команд бота
BUTTON_COMMANDS = {
    "📊 Расписание": "/schedule",
    "📝 Оценки": "/grades",
    "📝 Выставить оценки": "/grades",
    "🔔 Уведомления": "/notifications",
    "📸 Отметиться": "/checkin",
    "📋 Заявки": "/requests",
    "👥 Управление группами": "/manage_groups",
    "🔄 Создать QR-код": "/qr",
    "⚙️ Настройки системы": "/settings"
}

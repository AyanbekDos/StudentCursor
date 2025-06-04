# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from localization.kz_text import BUTTONS

def get_student_keyboard():
    """
    Создает клавиатуру для студента
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками для студента
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(BUTTONS["schedule"]), KeyboardButton(BUTTONS["grades"]))
    keyboard.add(KeyboardButton(BUTTONS["notifications"]), KeyboardButton(BUTTONS["checkin"]))
    keyboard.add(KeyboardButton(BUTTONS["delete_profile"]))
    return keyboard

def get_teacher_keyboard():
    """
    Создает клавиатуру для преподавателя
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками для преподавателя
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(BUTTONS["schedule"]), KeyboardButton(BUTTONS["set_grades"]))
    keyboard.add(KeyboardButton(BUTTONS["notifications"]), KeyboardButton(BUTTONS["requests"]))
    keyboard.add(KeyboardButton(BUTTONS["manage_groups"]), KeyboardButton(BUTTONS["create_qr"]))
    return keyboard

# Словарь соответствия текстовых команд и команд бота
BUTTON_COMMANDS = {
    BUTTONS["schedule"]: "/schedule",
    BUTTONS["grades"]: "/grades",
    BUTTONS["set_grades"]: "/grades",
    BUTTONS["notifications"]: "/notifications",
    BUTTONS["checkin"]: "/checkin",
    BUTTONS["requests"]: "/requests",
    BUTTONS["manage_groups"]: "/manage_groups",
    BUTTONS["create_qr"]: "/qr",
    BUTTONS["delete_profile"]: "/delete_profile"
}

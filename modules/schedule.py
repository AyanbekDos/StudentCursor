# schedule.py
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite

from database.db import db
from config import WEEKDAYS, SUBJECTS
from localization.kz_text import SCHEDULE_MESSAGES, BUTTONS, SCHEDULE_NOTIFICATIONS
from modules.notifications import send_schedule_notification
from modules.keyboards import get_teacher_keyboard

logger = logging.getLogger(__name__)

# Определение состояний для FSM
class ScheduleStates(StatesGroup):
    waiting_for_action = State()
    selecting_group = State()
    add_schedule_weekday = State()
    add_schedule_time = State()
    add_schedule_subject = State()
    edit_schedule_item = State()
    edit_schedule_weekday = State()
    edit_schedule_time = State()
    edit_schedule_subject = State()
    confirm_schedule_change = State()

# Клавиатура для действий с расписанием (для преподавателя)
def get_schedule_actions_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton(BUTTONS["view_schedule"]))
    keyboard.row(KeyboardButton(BUTTONS["add_lesson"]), KeyboardButton(BUTTONS["edit_schedule"]))
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Клавиатура для выбора дня недели
def get_weekday_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [KeyboardButton(day) for day in WEEKDAYS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Клавиатура для выбора предмета
def get_subject_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(subject) for subject in SUBJECTS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Клавиатура для подтверждения изменений
def get_confirm_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton(BUTTONS["confirm"]), KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Функция для форматирования расписания
def format_schedule(schedule_items):
    if not schedule_items:
        return SCHEDULE_MESSAGES["no_schedule"]
    
    # Группируем по дням недели
    weekday_schedule = {}
    for item in schedule_items:
        weekday = item["weekday"]
        if weekday not in weekday_schedule:
            weekday_schedule[weekday] = []
        weekday_schedule[weekday].append(item)
    
    # Сортируем дни недели
    weekday_order = {day: i for i, day in enumerate(WEEKDAYS)}
    sorted_weekdays = sorted(weekday_schedule.keys(), key=lambda d: weekday_order.get(d, 999))
    
    # Формируем текст расписания
    result = SCHEDULE_MESSAGES["schedule_title"] + "\n\n"
    
    for weekday in sorted_weekdays:
        result += f"📆 {weekday}:\n"
        # Сортируем занятия по времени
        day_items = sorted(weekday_schedule[weekday], key=lambda x: x["time"])
        for item in day_items:
            result += f"⏰ {item['time']} - {item['subject']}\n"
        result += "\n"
    
    return result

# Обработчик команды /schedule
async def cmd_schedule(message: types.Message, state: FSMContext):
    logger.info(f"Команда /schedule от пользователя {message.from_user.id}")
    user = await db.get_user(message.from_user.id)
    
    if not user or user["status"] != "approved":
        await message.answer(SCHEDULE_MESSAGES["not_registered"])
        return
    
    if user["role"] == "student":
        # Для студента просто показываем расписание его группы
        group_code = user["group_code"]
        schedule_items = await db.get_schedule(group_code)
        
        if not schedule_items:
            await message.answer(SCHEDULE_MESSAGES["no_schedule_created"].format(group_code=group_code))
        else:
            await message.answer(
                SCHEDULE_MESSAGES["schedule_for_group"].format(group_code=group_code) + 
                "\n\n" + format_schedule(schedule_items)
            )
    
    elif user["role"] == "teacher":
        # Для преподавателя показываем меню действий с расписанием
        await message.answer(
            SCHEDULE_MESSAGES["choose_action"],
            reply_markup=get_schedule_actions_keyboard()
        )
        await ScheduleStates.waiting_for_action.set()

# Обработчик выбора действия с расписанием
async def process_schedule_action(message: types.Message, state: FSMContext):
    logger.info(f"Выбрано действие с расписанием: {message.text}")
    action = message.text.lower()
    
    if action == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    # Сохраняем выбранное действие
    await state.update_data(action=action)
    
    user = await db.get_user(message.from_user.id)
    
    # Получаем группы преподавателя
    groups = await db.get_groups()
    available_groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
    
    if not available_groups:
        await message.answer(
            SCHEDULE_MESSAGES["no_groups_assigned"],
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.finish()
        return
    
    # Создаем клавиатуру с группами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for group in available_groups:
        keyboard.add(KeyboardButton(group["group_code"]))
    keyboard.add(KeyboardButton(BUTTONS["cancel"]))
    
    await message.answer(
        SCHEDULE_MESSAGES["choose_group_schedule"],
        reply_markup=keyboard
    )
    await ScheduleStates.selecting_group.set()

# Обработчик выбора группы для работы с расписанием
async def process_select_group(message: types.Message, state: FSMContext):
    logger.info(f"Выбрана группа для расписания: {message.text}")
    group_code = message.text.strip()
    
    if group_code.lower() == BUTTONS["cancel"].lower():
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=types.ReplyKeyboardRemove())
        return
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer(f"Топ {group_code} табылмады. Тізімнен топты таңдаңыз.")
        return
    
    # Сохраняем выбранную группу
    await state.update_data(group_code=group_code)
    
    # Получаем выбранное действие
    user_data = await state.get_data()
    action = user_data.get("action")
    
    if action == BUTTONS["view_schedule"].lower():
        schedule_items = await db.get_schedule(group_code)
        await message.answer(
            SCHEDULE_MESSAGES["schedule_for_group"].format(group_code=group_code) + 
            "\n\n" + format_schedule(schedule_items),
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.finish()
        
    elif action == BUTTONS["add_lesson"].lower():
        await message.answer(
            SCHEDULE_MESSAGES["choose_weekday"],
            reply_markup=get_weekday_keyboard()
        )
        await ScheduleStates.add_schedule_weekday.set()
        
    elif action == BUTTONS["edit_schedule"].lower():
        schedule_items = await db.get_schedule(group_code)
        
        if not schedule_items:
            await message.answer(
                SCHEDULE_MESSAGES["no_schedule_created"].format(group_code=group_code),
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            return
        
        # Создаем клавиатуру с элементами расписания
        keyboard = InlineKeyboardMarkup(row_width=1)
        for item in schedule_items:
            button_text = f"{item['weekday']} {item['time']} - {item['subject']}"
            callback_data = f"edit_schedule_{item['id']}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        await message.answer(
            SCHEDULE_MESSAGES["choose_lesson_edit"],
            reply_markup=keyboard
        )
        await ScheduleStates.edit_schedule_item.set()

# ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ ОБРАБОТЧИКИ

# Обработчик выбора дня недели для добавления сабака
async def process_add_weekday(message: types.Message, state: FSMContext):
    logger.info(f"Выбран день недели: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    weekday = message.text.strip()
    
    # Проверяем, что выбранный день недели корректный
    if weekday not in WEEKDAYS:
        await message.answer(
            "Тізімнен апта күнін таңдаңыз:",
            reply_markup=get_weekday_keyboard()
        )
        return
    
    # Сохраняем выбранный день недели
    await state.update_data(weekday=weekday)
    
    # Запрашиваем время
    await message.answer(
        SCHEDULE_MESSAGES["enter_time"],
        reply_markup=types.ReplyKeyboardRemove()
    )
    await ScheduleStates.add_schedule_time.set()

# Обработчик ввода времени
async def process_add_time(message: types.Message, state: FSMContext):
    logger.info(f"Введено время: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    time_str = message.text.strip()
    
    # Простая проверка формата времени
    if ":" not in time_str or len(time_str.split(":")) != 2:
        await message.answer(SCHEDULE_MESSAGES["invalid_time"])
        return
    
    try:
        hours, minutes = time_str.split(":")
        hours = int(hours)
        minutes = int(minutes)
        
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError("Invalid time range")
            
    except ValueError:
        await message.answer(SCHEDULE_MESSAGES["invalid_time"])
        return
    
    # Сохраняем время
    await state.update_data(time=time_str)
    
    # Запрашиваем предмет
    await message.answer(
        SCHEDULE_MESSAGES["choose_subject"],
        reply_markup=get_subject_keyboard()
    )
    await ScheduleStates.add_schedule_subject.set()

# Обработчик выбора предмета
async def process_add_subject(message: types.Message, state: FSMContext):
    logger.info(f"Выбран предмет: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    subject = message.text.strip()
    
    # Проверяем, что предмет из списка
    if subject not in SUBJECTS:
        await message.answer(
            "Тізімнен пәнді таңдаңыз:",
            reply_markup=get_subject_keyboard()
        )
        return
    
    # Получаем все данные из состояния
    data = await state.get_data()
    group_code = data["group_code"]
    weekday = data["weekday"]
    time = data["time"]
    
    # Показываем подтверждение
    await message.answer(
        SCHEDULE_MESSAGES["confirm_add_lesson"].format(
            group_code=group_code,
            weekday=weekday,
            time=time,
            subject=subject
        ),
        reply_markup=get_confirm_keyboard()
    )
    
    # Сохраняем предмет
    await state.update_data(subject=subject)
    await ScheduleStates.confirm_schedule_change.set()

# Обработчик подтверждения добавления урока
async def process_confirm_add_lesson(message: types.Message, state: FSMContext):
    logger.info(f"Подтверждение добавления урока: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(SCHEDULE_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    if message.text.strip() == BUTTONS["confirm"]:
        # Получаем все данные
        data = await state.get_data()
        group_code = data["group_code"]
        weekday = data["weekday"]
        time = data["time"]
        subject = data["subject"]
        
        # Добавляем урок в расписание
        await db.add_schedule_item(group_code, weekday, time, subject)
        
        # Отправляем уведомления студентам
        students_count = await send_schedule_notification(
            message.bot, group_code, "add", weekday, time, subject
        )
        
        keyboard = get_teacher_keyboard()
        await message.answer(
            SCHEDULE_MESSAGES["lesson_added"].format(
                group_code=group_code,
                students_count=students_count
            ),
            reply_markup=keyboard
        )
        await state.finish()
    else:
        # Неправильный ответ
        await message.answer(
            "Растау немесе болдырмау батырмасын басыңыз:",
            reply_markup=get_confirm_keyboard()
        )

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    logger.info("Регистрация обработчиков schedule.py")
    
    dp.register_message_handler(cmd_schedule, commands=["schedule"], state="*")
    dp.register_message_handler(process_schedule_action, state=ScheduleStates.waiting_for_action)
    dp.register_message_handler(process_select_group, state=ScheduleStates.selecting_group)
    
    # ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ ОБРАБОТЧИКИ
    dp.register_message_handler(process_add_weekday, state=ScheduleStates.add_schedule_weekday)
    dp.register_message_handler(process_add_time, state=ScheduleStates.add_schedule_time)
    dp.register_message_handler(process_add_subject, state=ScheduleStates.add_schedule_subject)
    dp.register_message_handler(process_confirm_add_lesson, state=ScheduleStates.confirm_schedule_change)
    
    logger.info("Все обработчики schedule.py зарегистрированы")

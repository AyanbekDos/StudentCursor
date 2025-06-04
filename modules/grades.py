# grades.py
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

from database.db import db
from config import SUBJECTS
from localization.kz_text import GRADES_MESSAGES, BUTTONS, GRADE_EMOJIS
from modules.notifications import send_personal_notification
from modules.keyboards import get_student_keyboard, get_teacher_keyboard

# Определение состояний для FSM
class GradeStates(StatesGroup):
    waiting_for_action = State()
    select_group = State()
    select_student = State()
    select_subject = State()
    input_grade = State()
    input_comment = State()

# Клавиатура для действий с оценками
def get_grades_actions_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton(BUTTONS["my_grades"]))
    keyboard.row(KeyboardButton(BUTTONS["set_grade"]))
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Клавиатура для выбора предмета
def get_subject_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(subject) for subject in SUBJECTS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Клавиатура для выбора оценки
def get_grade_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=5)
    keyboard.row(
        KeyboardButton("0"),
        KeyboardButton("25"),
        KeyboardButton("50"),
        KeyboardButton("75"),
        KeyboardButton("100")
    )
    keyboard.row(
        KeyboardButton("10"),
        KeyboardButton("30"),
        KeyboardButton("60"),
        KeyboardButton("80"),
        KeyboardButton("90")
    )
    keyboard.row(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Функция для форматирования оценок студента
def format_grades(grades):
    if not grades:
        return GRADES_MESSAGES["no_grades"]
    
    # Группируем оценки по предметам
    subjects_grades = {}
    for grade_item in grades:
        subject = grade_item["subject"]
        if subject not in subjects_grades:
            subjects_grades[subject] = []
        subjects_grades[subject].append(grade_item)
    
    # Формируем текст с оценками
    result = GRADES_MESSAGES["grades_title"] + "\n\n"
    
    for subject, grade_items in subjects_grades.items():
        result += f"📚 {subject}:\n"
        for item in sorted(grade_items, key=lambda x: x["date"], reverse=True):
            grade = item["grade"]
            date = item["date"]
            comment = item["comment"] or ""
            
            # Добавляем эмодзи в зависимости от оценки
            grade_emoji = GRADE_EMOJIS["unknown"]
            if grade >= 90:
                grade_emoji = GRADE_EMOJIS["excellent"]
            elif grade >= 75:
                grade_emoji = GRADE_EMOJIS["good"]
            elif grade >= 50:
                grade_emoji = GRADE_EMOJIS["satisfactory"]
            elif grade >= 25:
                grade_emoji = GRADE_EMOJIS["poor"]
            else:
                grade_emoji = GRADE_EMOJIS["very_poor"]
            
            result += f"{grade_emoji} {date}: {grade} ұпай"
            if comment:
                result += f" ({comment})"
            result += "\n"
        result += "\n"
    
    return result

# Функция для форматирования оценок, выставленных преподавателем
def format_teacher_grades(grades, max_grades_per_student=3):
    if not grades:
        return GRADES_MESSAGES["no_grades_set"]
    
    # Группируем оценки по группам и студентам
    groups_students = {}
    for grade_item in grades:
        group_code = grade_item["group_code"]
        student_name = grade_item["full_name"]
        student_id = grade_item["student_id"]
        
        if group_code not in groups_students:
            groups_students[group_code] = {}
        
        if student_id not in groups_students[group_code]:
            groups_students[group_code][student_id] = {
                "name": student_name,
                "grades": []
            }
        
        groups_students[group_code][student_id]["grades"].append({
            "subject": grade_item["subject"],
            "grade": grade_item["grade"],
            "date": grade_item["date"],
            "comment": grade_item["comment"]
        })
    
    # Формируем текст с оценками по группам и студентам
    result = GRADES_MESSAGES["teacher_grades_title"] + "\n\n"
    
    # Сортируем группы по алфавиту
    for group_code in sorted(groups_students.keys()):
        result += f"📁 Топ: {group_code}\n"
        
        # Сортируем студентов по имени
        students = groups_students[group_code]
        for student_id in sorted(students.keys(), key=lambda sid: students[sid]["name"]):
            student_data = students[student_id]
            result += f"👤 {student_data['name']}:\n"
            
            # Собираем все оценки студента и сортируем по дате
            all_grades = sorted(student_data["grades"], key=lambda g: g["date"], reverse=True)
            
            # Ограничиваем количество отображаемых оценок
            for i, grade in enumerate(all_grades[:max_grades_per_student]):
                subject = grade["subject"]
                grade_value = grade["grade"]
                date = grade["date"]
                comment = grade["comment"] or ""
                
                # Добавляем эмодзи в зависимости от оценки
                grade_emoji = GRADE_EMOJIS["unknown"]
                if grade_value >= 90:
                    grade_emoji = GRADE_EMOJIS["excellent"]
                elif grade_value >= 75:
                    grade_emoji = GRADE_EMOJIS["good"]
                elif grade_value >= 50:
                    grade_emoji = GRADE_EMOJIS["satisfactory"]
                elif grade_value >= 25:
                    grade_emoji = GRADE_EMOJIS["poor"]
                else:
                    grade_emoji = GRADE_EMOJIS["very_poor"]
                
                result += f" {grade_emoji} {subject}, {date}: {grade_value} ұпай"
                if comment:
                    result += f" ({comment})"
                result += "\n"
            
            # Если есть еще оценки, показываем сколько еще осталось
            if len(all_grades) > max_grades_per_student:
                result += f" ... және тағы {len(all_grades) - max_grades_per_student} баға\n"
            
            result += "\n"
    
    # Добавляем пояснение о показе только последних оценок
    result += f"\n{GRADES_MESSAGES['last_grades_shown'].format(count=max_grades_per_student)}"
    
    return result

# Обработчик команды /grades
async def cmd_grades(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    
    if not user or user["status"] != "approved":
        await message.answer(GRADES_MESSAGES["not_registered"])
        return
    
    # Разные действия в зависимости от роли
    if user["role"] == "student":
        # Для студента показываем его оценки
        grades = await db.get_student_grades(message.from_user.id)
        await message.answer(format_grades(grades))
        
    elif user["role"] == "teacher":
        # Для преподавателя показываем меню действий с оценками
        await message.answer(
            GRADES_MESSAGES["choose_action"],
            reply_markup=get_grades_actions_keyboard()
        )
        await GradeStates.waiting_for_action.set()

# Обработчик выбора действия с оценками
async def process_grades_action(message: types.Message, state: FSMContext):
    action = message.text.lower()
    
    if action == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GRADES_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    if action == BUTTONS["my_grades"].lower():
        # Для преподавателя показываем оценки, которые он выставил студентам
        keyboard = get_teacher_keyboard()
        teacher_grades = await db.get_teacher_grades(message.from_user.id)
        await message.answer(format_teacher_grades(teacher_grades), reply_markup=keyboard)
        await state.finish()
        
    elif action == BUTTONS["set_grade"].lower():
        user = await db.get_user(message.from_user.id)
        
        # Получаем группы преподавателя
        groups = await db.get_groups()
        teacher_groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
        
        if not teacher_groups:
            keyboard = get_teacher_keyboard()
            await message.answer(
                GRADES_MESSAGES["no_assigned_groups"],
                reply_markup=keyboard
            )
            await state.finish()
            return
        
        # Создаем клавиатуру с группами
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for group in teacher_groups:
            keyboard.add(KeyboardButton(group["group_code"]))
        keyboard.add(KeyboardButton(BUTTONS["cancel"]))
        
        await message.answer(
            GRADES_MESSAGES["choose_group_grades"],
            reply_markup=keyboard
        )
        await GradeStates.select_group.set()

# Обработчик выбора группы для выставления оценок
async def process_select_group(message: types.Message, state: FSMContext):
    group_code = message.text.strip()
    
    if group_code.lower() == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GRADES_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer(f"Топ {group_code} табылмады. Тізімнен топты таңдаңыз.")
        return
    
    # Получаем список студентов выбранной группы
    students = await db.get_students_by_group(group_code)
    
    if not students:
        keyboard = get_teacher_keyboard()
        await message.answer(
            GRADES_MESSAGES["no_students_group"].format(group_code=group_code),
            reply_markup=keyboard
        )
        await state.finish()
        return
    
    # Создаем клавиатуру с кнопками выбора студента
    keyboard = InlineKeyboardMarkup(row_width=1)
    for student in students:
        button_text = f"{student['full_name']}"
        callback_data = f"grade_student_{student['telegram_id']}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
    
    # Сохраняем выбранную группу в состоянии
    await state.update_data(group_code=group_code)
    
    await message.answer(
        GRADES_MESSAGES["choose_student_grade"],
        reply_markup=keyboard
    )
    await GradeStates.select_student.set()

# Обработчик выбора студента для выставления оценки
async def process_select_student(callback_query: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID студента из callback_data
    student_id = int(callback_query.data.split("_")[2])
    
    # Получаем информацию о студенте
    student = await db.get_user(student_id)
    
    if not student or student["role"] != "student" or student["status"] != "approved":
        await callback_query.answer(GRADES_MESSAGES["student_not_found"])
        await state.finish()
        return
    
    # Сохраняем данные о выбранном студенте
    await state.update_data(student_id=student_id, student_name=student["full_name"])
    
    # Показываем клавиатуру для выбора предмета
    await callback_query.message.answer(
        GRADES_MESSAGES["student_selected"].format(student_name=student['full_name']),
        reply_markup=get_subject_keyboard()
    )
    
    await GradeStates.select_subject.set()
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback_query.answer()

# Обработчик выбора предмета для выставления оценки
async def process_select_subject(message: types.Message, state: FSMContext):
    subject = message.text
    
    if subject.lower() == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GRADES_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    # Валидация предмета
    if subject not in SUBJECTS:
        await message.answer(
            "Тізімнен пәнді таңдаңыз:",
            reply_markup=get_subject_keyboard()
        )
        return
    
    # Сохраняем выбранный предмет
    await state.update_data(subject=subject)
    
    # Запрашиваем оценку
    await message.answer(
        GRADES_MESSAGES["choose_grade"],
        reply_markup=get_grade_keyboard()
    )
    await GradeStates.input_grade.set()

# Обработчик ввода оценки
async def process_input_grade(message: types.Message, state: FSMContext):
    try:
        grade = int(message.text)
        # Проверяем диапазон оценок (от 0 до 100)
        if grade < 0 or grade > 100:
            raise ValueError("Grade out of range")
    except ValueError:
        if message.text.lower() == BUTTONS["cancel"].lower():
            keyboard = get_teacher_keyboard()
            await state.finish()
            await message.answer(GRADES_MESSAGES["action_cancelled"], reply_markup=keyboard)
            return
        
        await message.answer(
            GRADES_MESSAGES["invalid_grade"],
            reply_markup=get_grade_keyboard()
        )
        return
    
    # Сохраняем выбранную оценку
    await state.update_data(grade=grade)
    
    # Запрашиваем комментарий (опционально)
    await message.answer(
        GRADES_MESSAGES["enter_comment"],
        reply_markup=types.ReplyKeyboardRemove()
    )
    await GradeStates.input_comment.set()

# Обработчик ввода комментария к оценке
async def process_input_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    
    if comment.lower() == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GRADES_MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    # Если пользователь отправил "-", то комментария нет
    if comment == "-":
        comment = None
    
    # Получаем все данные из состояния
    data = await state.get_data()
    student_id = data["student_id"]
    student_name = data["student_name"]
    subject = data["subject"]
    grade = data["grade"]
    
    # Текущая дата в формате ДД.ММ.ГГГГ
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Выставляем оценку
    await db.add_grade(student_id, subject, today, grade, comment)
    
    keyboard = get_teacher_keyboard()
    
    # Уведомляем преподавателя
    await message.answer(
        GRADES_MESSAGES["grade_set"].format(
            student_name=student_name,
            subject=subject,
            date=today,
            grade=grade
        ) + (f"\nТүсініктеме: {comment}" if comment else ""),
        reply_markup=keyboard
    )
    
    # Отправляем уведомление студенту
    notification_text = GRADES_MESSAGES["grade_notification"].format(
        subject=subject,
        date=today,
        grade=grade
    ) + (f"\nТүсініктеме: {comment}" if comment else "")
    
    # Используем функцию отправки персонального уведомления с типом "grade"
    notification_sent = await send_personal_notification(
        message.bot,
        student_id,
        notification_text,
        notification_type="grade"
    )
    
    if not notification_sent:
        await message.answer(GRADES_MESSAGES["notification_failed"])
    
    # Сбрасываем состояние
    await state.finish()

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    dp.register_message_handler(cmd_grades, commands=["grades"], state="*")
    dp.register_message_handler(process_grades_action, state=GradeStates.waiting_for_action)
    dp.register_message_handler(process_select_group, state=GradeStates.select_group)
    dp.register_callback_query_handler(
        process_select_student,
        lambda c: c.data.startswith("grade_student_"),
        state=GradeStates.select_student
    )
    dp.register_message_handler(process_select_subject, state=GradeStates.select_subject)
    dp.register_message_handler(process_input_grade, state=GradeStates.input_grade)
    dp.register_message_handler(process_input_comment, state=GradeStates.input_comment)

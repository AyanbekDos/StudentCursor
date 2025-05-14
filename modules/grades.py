from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

from database.db import db
from config import SUBJECTS
from modules.notifications import send_personal_notification

# Определение состояний для FSM
class GradeStates(StatesGroup):
    waiting_for_action = State()
    select_group = State()  # Новое состояние для выбора группы
    select_student = State()
    select_subject = State()
    input_grade = State()
    input_comment = State()

# Клавиатура для действий с оценками
def get_grades_actions_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("Мои оценки"))
    keyboard.row(KeyboardButton("Выставить оценку"))
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Клавиатура для выбора предмета
def get_subject_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(subject) for subject in SUBJECTS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Клавиатура для выбора оценки
def get_grade_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=5)
    # Добавляем кнопки с разными вариантами оценок
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
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Функция для форматирования оценок студента
def format_grades(grades):
    if not grades:
        return "У вас пока нет оценок."
    
    # Группируем оценки по предметам
    subjects_grades = {}
    for grade_item in grades:
        subject = grade_item["subject"]
        if subject not in subjects_grades:
            subjects_grades[subject] = []
        subjects_grades[subject].append(grade_item)
    
    # Формируем текст с оценками
    result = "📊 ВАШИ ОЦЕНКИ:\n\n"
    for subject, grade_items in subjects_grades.items():
        result += f"📚 {subject}:\n"
        
        for item in sorted(grade_items, key=lambda x: x["date"], reverse=True):
            grade = item["grade"]
            date = item["date"]
            comment = item["comment"] or ""
            
            # Добавляем эмодзи в зависимости от оценки (100-балльная система)
            grade_emoji = "❓"
            if grade >= 90:
                grade_emoji = "🌟"  # Отлично (90-100)
            elif grade >= 75:
                grade_emoji = "✅"  # Хорошо (75-89)
            elif grade >= 50:
                grade_emoji = "⚠️"  # Удовлетворительно (50-74)
            elif grade >= 25:
                grade_emoji = "⛔"  # Плохо (25-49)
            else:
                grade_emoji = "❌"  # Очень плохо (0-24)
            
            result += f"{grade_emoji} {date}: {grade} баллов"
            if comment:
                result += f" ({comment})"
            result += "\n"
        
        result += "\n"
    
    return result

# Функция для форматирования оценок, выставленных преподавателем
def format_teacher_grades(grades, max_grades_per_student=3):
    if not grades:
        return "Вы еще не выставили ни одной оценки."
    
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
    result = "📊 ПОСЛЕДНИЕ ВЫСТАВЛЕННЫЕ ВАМИ ОЦЕНКИ:\n\n"
    
    # Сортируем группы по алфавиту
    for group_code in sorted(groups_students.keys()):
        result += f"📁 Группа: {group_code}\n"
        
        # Сортируем студентов по имени
        students = groups_students[group_code]
        for student_id in sorted(students.keys(), key=lambda sid: students[sid]["name"]):
            student_data = students[student_id]
            result += f"👤 {student_data['name']}:\n"
            
            # Собираем все оценки студента и сортируем по дате (сначала новые)
            all_grades = sorted(student_data["grades"], key=lambda g: g["date"], reverse=True)
            
            # Ограничиваем количество отображаемых оценок
            for i, grade in enumerate(all_grades[:max_grades_per_student]):
                subject = grade["subject"]
                grade_value = grade["grade"]
                date = grade["date"]
                comment = grade["comment"] or ""
                
                # Добавляем эмодзи в зависимости от оценки
                grade_emoji = "❓"
                if grade_value >= 90:
                    grade_emoji = "🌟"  # Отлично (90-100)
                elif grade_value >= 75:
                    grade_emoji = "✅"  # Хорошо (75-89)
                elif grade_value >= 50:
                    grade_emoji = "⚠️"  # Удовлетворительно (50-74)
                elif grade_value >= 25:
                    grade_emoji = "⛔"  # Плохо (25-49)
                else:
                    grade_emoji = "❌"  # Очень плохо (0-24)
                
                result += f"  {grade_emoji} {subject}, {date}: {grade_value} баллов"
                if comment:
                    result += f" ({comment})"
                result += "\n"
            
            # Если есть еще оценки, показываем сколько еще осталось
            if len(all_grades) > max_grades_per_student:
                result += f"  ... и еще {len(all_grades) - max_grades_per_student} оценок\n"
            
            result += "\n"
    
    # Добавляем пояснение о показе только последних оценок
    result += f"\nПоказаны последние {max_grades_per_student} оценок для каждого студента."
    
    return result

# Обработчик команды /grades
async def cmd_grades(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    
    if not user or user["status"] != "approved":
        await message.answer("Вы не зарегистрированы в системе или ваша заявка еще не подтверждена.")
        return
    
    # Разные действия в зависимости от роли
    if user["role"] == "student":
        # Для студента показываем его оценки
        grades = await db.get_student_grades(message.from_user.id)
        await message.answer(format_grades(grades))
    
    elif user["role"] in ["teacher", "admin"]:
        # Для преподавателя показываем меню действий с оценками
        await message.answer(
            "Выберите действие:",
            reply_markup=get_grades_actions_keyboard()
        )
        await GradeStates.waiting_for_action.set()

# Обработчик выбора действия с оценками
async def process_grades_action(message: types.Message, state: FSMContext):
    action = message.text.lower()
    
    if action == "отмена":
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
        
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard, get_student_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = get_student_keyboard()
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    if action == "мои оценки":
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
        
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard, get_student_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
            # Для преподавателя показываем оценки, которые он выставил студентам
            teacher_grades = await db.get_teacher_grades(message.from_user.id)
            await message.answer(format_teacher_grades(teacher_grades), reply_markup=keyboard)
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
            # Для админа показываем сообщение, что у него нет оценок
            await message.answer("У администраторов нет оценок. Вы можете выставлять оценки студентам.", reply_markup=keyboard)
        else:
            # Для студента показываем его оценки
            keyboard = get_student_keyboard()
            grades = await db.get_student_grades(message.from_user.id)
            await message.answer(format_grades(grades), reply_markup=keyboard)
            
        await state.finish()
    
    elif action == "выставить оценку":
        user = await db.get_user(message.from_user.id)
        
        if user["role"] == "teacher":
            # Получаем группы преподавателя
            groups = await db.get_groups()
            teacher_groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
            
            if not teacher_groups:
                # Возвращаем клавиатуру преподавателя
                from modules.keyboards import get_teacher_keyboard
                keyboard = get_teacher_keyboard()
                
                await message.answer(
                    "У вас нет закрепленных групп. Подтвердите хотя бы одного студента или добавьте новую группу.", 
                    reply_markup=keyboard
                )
                await state.finish()
                return
            
            # Создаем клавиатуру с группами
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            for group in teacher_groups:
                keyboard.add(KeyboardButton(group["group_code"]))
            keyboard.add(KeyboardButton("Отмена"))
            
            await message.answer(
                "Выберите группу для выставления оценок:",
                reply_markup=keyboard
            )
            
            await GradeStates.select_group.set()
            
        else:  # Для админа
            # Получаем все группы
            groups = await db.get_groups()
            
            if not groups:
                # Возвращаем клавиатуру админа
                from modules.keyboards import get_admin_keyboard
                keyboard = get_admin_keyboard()
                
                await message.answer(
                    "В системе пока нет ни одной группы.", 
                    reply_markup=keyboard
                )
                await state.finish()
                return
            
            # Создаем клавиатуру с группами
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            for group in groups:
                keyboard.add(KeyboardButton(group["group_code"]))
            keyboard.add(KeyboardButton("Отмена"))
            
            await message.answer(
                "Выберите группу для выставления оценок:",
                reply_markup=keyboard
            )
            
            await GradeStates.select_group.set()

# Обработчик выбора группы для выставления оценок
async def process_select_group(message: types.Message, state: FSMContext):
    group_code = message.text.strip()
    
    if group_code.lower() == "отмена":
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
        
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer(f"Группа {group_code} не найдена. Пожалуйста, выберите группу из списка.")
        return
    
    # Получаем список студентов выбранной группы
    students = await db.get_students_by_group(group_code)
    
    if not students:
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
        
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await message.answer(
            f"В группе {group_code} пока нет подтвержденных студентов.",
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
        f"Выберите студента для выставления оценки:",
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
        await callback_query.answer("Ошибка: студент не найден.")
        await state.finish()
        return
    
    # Сохраняем данные о выбранном студенте
    await state.update_data(student_id=student_id, student_name=student["full_name"])
    
    # Показываем клавиатуру для выбора предмета
    await callback_query.message.answer(
        f"Выбран студент: {student['full_name']}\n"
        f"Выберите предмет для выставления оценки:",
        reply_markup=get_subject_keyboard()
    )
    await GradeStates.select_subject.set()
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback_query.answer()

# Обработчик выбора предмета для выставления оценки
async def process_select_subject(message: types.Message, state: FSMContext):
    subject = message.text
        
    if subject.lower() == "отмена":
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
            
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard, get_student_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = get_student_keyboard()
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
        
    # Валидация предмета
    if subject not in SUBJECTS:
        await message.answer("Пожалуйста, выберите предмет из списка:", reply_markup=get_subject_keyboard())
        return
        
    
    # Сохраняем выбранный предмет
    await state.update_data(subject=subject)
    
    # Запрашиваем оценку
    await message.answer(
        "Выберите оценку для студента:",
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
        if message.text.lower() == "отмена":
            # Получаем данные пользователя
            user = await db.get_user(message.from_user.id)
            
            # Выбираем клавиатуру в зависимости от роли пользователя
            from modules.keyboards import get_teacher_keyboard, get_admin_keyboard
            
            if user["role"] == "teacher":
                keyboard = get_teacher_keyboard()
            elif user["role"] == "admin":
                keyboard = get_admin_keyboard()
            else:
                keyboard = None
                
            await state.finish()
            await message.answer("Выставление оценки отменено.", reply_markup=keyboard)
            return
        
        await message.answer("Пожалуйста, введите корректную оценку от 0 до 100 баллов:", reply_markup=get_grade_keyboard())
        return
    
    # Сохраняем выбранную оценку
    await state.update_data(grade=grade)
    
    # Запрашиваем комментарий (опционально)
    await message.answer(
        "Введите комментарий к оценке (или отправьте '-' для пропуска):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await GradeStates.input_comment.set()

# Обработчик ввода комментария к оценке
async def process_input_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    
    if comment.lower() == "отмена":
        # Получаем данные пользователя
        user = await db.get_user(message.from_user.id)
        
        # Выбираем клавиатуру в зависимости от роли пользователя
        from modules.keyboards import get_teacher_keyboard, get_admin_keyboard
        
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Выставление оценки отменено.", reply_markup=keyboard)
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
    
    # Получаем данные пользователя
    user = await db.get_user(message.from_user.id)
    
    # Выбираем клавиатуру в зависимости от роли пользователя
    from modules.keyboards import get_teacher_keyboard, get_admin_keyboard
    
    if user["role"] == "teacher":
        keyboard = get_teacher_keyboard()
    elif user["role"] == "admin":
        keyboard = get_admin_keyboard()
    else:
        keyboard = None
        
    # Уведомляем преподавателя
    await message.answer(
        f"Оценка выставлена:\n"
        f"Студент: {student_name}\n"
        f"Предмет: {subject}\n"
        f"Дата: {today}\n"
        f"Оценка: {grade}"
        + (f"\nКомментарий: {comment}" if comment else ""),
        reply_markup=keyboard
    )
    
    # Отправляем уведомление студенту
    notification_text = (
        f"Вам выставлена новая оценка по предмету {subject}:\n"
        f"Дата: {today}\n"
        f"Оценка: {grade}"
        + (f"\nКомментарий: {comment}" if comment else "")
    )
    
    # Используем функцию отправки персонального уведомления с типом "grade"
    notification_sent = await send_personal_notification(
        message.bot, 
        student_id, 
        notification_text, 
        notification_type="grade"
    )
    
    if not notification_sent:
        await message.answer("Не удалось отправить уведомление студенту, но оценка выставлена.")
    
    # Сбрасываем состояние
    await state.finish()

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    dp.register_message_handler(cmd_grades, commands=["grades"], state="*")
    dp.register_message_handler(process_grades_action, state=GradeStates.waiting_for_action)
    dp.register_message_handler(process_select_group, state=GradeStates.select_group)  # Добавляем обработчик выбора группы
    dp.register_callback_query_handler(
        process_select_student, 
        lambda c: c.data.startswith("grade_student_"), 
        state=GradeStates.select_student
    )
    dp.register_message_handler(process_select_subject, state=GradeStates.select_subject)
    dp.register_message_handler(process_input_grade, state=GradeStates.input_grade)
    dp.register_message_handler(process_input_comment, state=GradeStates.input_comment) 
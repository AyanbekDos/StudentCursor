from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from config import ROLES, TEACHER_CODE, ADMIN_CODE
from modules.keyboards import get_student_keyboard, get_teacher_keyboard, get_admin_keyboard
from modules.notifications import send_group_change_notification

# Определение состояний для FSM
class RegistrationStates(StatesGroup):
    choose_role = State()
    enter_fullname = State()
    enter_group = State()
    enter_teacher_code = State()
    enter_admin_code = State()

# Состояния для управления группами
class GroupManagementStates(StatesGroup):
    choosing_action = State()
    selecting_group = State()
    selecting_student = State()
    selecting_new_group = State()
    confirming_transfer = State()
    entering_new_group_code = State()

# Клавиатура для выбора роли
def get_role_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton(ROLES["student"]))
    keyboard.add(KeyboardButton(ROLES["teacher"]))
    return keyboard

# Обработчик команды /start
async def cmd_start(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    
    if user:
        # Пользователь уже зарегистрирован
        status = user["status"]
        role = user["role"]
        
        if status == "pending":
            await message.answer(
                "Вы уже зарегистрированы, но ваша заявка ещё не рассмотрена. "
                "Пожалуйста, ожидайте подтверждения."
            )
        elif status == "approved":
            if role == "student":
                # Используем клавиатуру студента
                keyboard = get_student_keyboard()
                await message.answer(
                    f"Добро пожаловать, {user['full_name']}!\n"
                    f"Вы зарегистрированы как студент группы {user['group_code']}.",
                    reply_markup=keyboard
                )
            elif role == "teacher":
                # Используем клавиатуру преподавателя
                keyboard = get_teacher_keyboard()
                await message.answer(
                    f"Добро пожаловать, {user['full_name']}!\n"
                    f"Вы зарегистрированы как преподаватель.",
                    reply_markup=keyboard
                )
            elif role == "admin":
                # Используем клавиатуру администратора
                keyboard = get_admin_keyboard()
                await message.answer(
                    f"Добро пожаловать, {user['full_name']}!\n"
                    f"Вы зарегистрированы как администратор.",
                    reply_markup=keyboard
                )
        elif status == "rejected":
            await message.answer(
                "Ваша заявка была отклонена. Если вы считаете, что произошла ошибка, "
                "обратитесь к администратору."
            )
    else:
        # Начинаем регистрацию
        await message.answer(
            "Добро пожаловать в систему учёта студентов и преподавателей! "
            "Для начала выберите вашу роль:",
            reply_markup=get_role_keyboard()
        )
        await RegistrationStates.choose_role.set()

# Обработчик выбора роли
async def process_role_selection(message: types.Message, state: FSMContext):
    selected_role = None
    
    for role_key, role_name in ROLES.items():
        if message.text == role_name:
            selected_role = role_key
            break
    
    if not selected_role:
        await message.answer("Пожалуйста, выберите роль, используя кнопки ниже:", 
                           reply_markup=get_role_keyboard())
        return
    
    # Сохраняем выбранную роль
    await state.update_data(role=selected_role)
    
    # Запрашиваем ФИО
    await message.answer("Введите ваше полное имя (ФИО):", reply_markup=types.ReplyKeyboardRemove())
    await RegistrationStates.enter_fullname.set()

# Обработчик ввода ФИО
async def process_fullname(message: types.Message, state: FSMContext):
    fullname = message.text.strip()
    
    if len(fullname.split()) < 2:
        await message.answer("Пожалуйста, введите полное ФИО (фамилия и имя обязательны):")
        return
    
    # Сохраняем ФИО
    await state.update_data(fullname=fullname)
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    role = user_data["role"]
    
    if role == "student":
        # Запрашиваем код группы для студента
        await message.answer("Введите код вашей группы (например, ИС-21):")
        await RegistrationStates.enter_group.set()
    elif role == "teacher":
        # Запрашиваем секретный код для преподавателя
        await message.answer("Введите секретный код для регистрации преподавателя:")
        await RegistrationStates.enter_teacher_code.set()
    elif role == "admin":
        # Запрашиваем код администратора
        await message.answer("Введите секретный код для регистрации администратора:")
        await RegistrationStates.enter_admin_code.set()

# Обработчик ввода кода группы
async def process_group_code(message: types.Message, state: FSMContext):
    group_code = message.text.strip().upper()
    
    # Сохраняем код группы
    await state.update_data(group_code=group_code)
    
    # Получаем данные пользователя
    user_data = await state.get_data()
    
    # Регистрируем студента (статус "pending" - ожидает подтверждения)
    await db.add_user(
        telegram_id=message.from_user.id,
        full_name=user_data["fullname"],
        role=user_data["role"],
        group_code=group_code
    )
    
    # Проверяем, существует ли группа, если нет - создаем
    groups = await db.get_groups()
    group_exists = False
    
    for group in groups:
        if group["group_code"] == group_code:
            group_exists = True
            break
    
    if not group_exists:
        await db.add_group(group_code)
    
    # Уведомляем пользователя
    await message.answer(
        f"Спасибо за регистрацию, {user_data['fullname']}!\n"
        f"Ваша заявка на регистрацию в группе {group_code} отправлена "
        f"преподавателю и ожидает подтверждения."
    )
    
    # Сбрасываем состояние
    await state.finish()

# Обработчик ввода кода преподавателя
async def process_teacher_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    
    if code != TEACHER_CODE:
        await message.answer("Неверный код. Пожалуйста, попробуйте снова или обратитесь к администратору:")
        return
    
    # Получаем данные пользователя
    user_data = await state.get_data()
    
    # Регистрируем преподавателя (сразу со статусом "approved")
    await db.add_user(
        telegram_id=message.from_user.id,
        full_name=user_data["fullname"],
        role=user_data["role"],
        status="approved"
    )
    
    # Уведомляем пользователя
    await message.answer(
        f"Спасибо за регистрацию, {user_data['fullname']}!\n"
        f"Вы зарегистрированы как преподаватель."
    )
    
    # Сбрасываем состояние
    await state.finish()

# Обработчик ввода кода администратора
async def process_admin_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    
    if code != ADMIN_CODE:
        await message.answer("Неверный код администратора. Пожалуйста, попробуйте снова:")
        return
    
    # Получаем данные пользователя
    user_data = await state.get_data()
    
    # Регистрируем администратора (сразу со статусом "approved")
    await db.add_user(
        telegram_id=message.from_user.id,
        full_name=user_data["fullname"],
        role=user_data["role"],
        status="approved"
    )
    
    # Уведомляем пользователя
    await message.answer(
        f"Спасибо за регистрацию, {user_data['fullname']}!\n"
        f"Вы зарегистрированы как администратор."
    )
    
    # Сбрасываем состояние
    await state.finish()

# Функция для создания клавиатуры с заявками на подтверждение
async def get_pending_students_keyboard():
    pending_students = await db.get_pending_students()
    
    if not pending_students:
        return None
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for student in pending_students:
        button_text = f"{student['full_name']} - {student['group_code']}"
        callback_data = f"approve_{student['telegram_id']}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
    
    return keyboard

# Обработчик команды для просмотра заявок (для преподавателя)
async def cmd_pending_requests(message: types.Message):
    user = await db.get_user(message.from_user.id)
    
    # Проверяем, что пользователь - преподаватель или админ
    if not user or (user['role'] != 'teacher' and user['role'] != 'admin'):
        await message.answer("Эта команда доступна только для преподавателей и администраторов.")
        return
    
    # Получаем список заявок на подтверждение
    keyboard = await get_pending_students_keyboard()
    
    if keyboard.inline_keyboard:
        await message.answer("Список заявок на подтверждение:", reply_markup=keyboard)
    else:
        # Возвращаем клавиатуру в зависимости от роли пользователя
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        else:  # admin
            keyboard = get_admin_keyboard()
            
        await message.answer("Заявок на подтверждение нет.", reply_markup=keyboard)

# Обработчик кнопки "Заявки"
async def cmd_requests(message: types.Message, state: FSMContext = None):
    """
    Обрабатывает нажатие на кнопку "Заявки" или команду /requests
    Перенаправляет на функцию cmd_pending_requests
    """
    # Просто вызываем существующую функцию
    await cmd_pending_requests(message)

# Обработчик нажатия на кнопку подтверждения регистрации
async def process_approve_button(callback_query: types.CallbackQuery):
    # Извлекаем ID студента из callback_data
    student_id = int(callback_query.data.split("_")[1])
    
    # Получаем данные студента и учителя
    student = await db.get_user(student_id)
    teacher = await db.get_user(callback_query.from_user.id)
    
    if not student or not teacher:
        await callback_query.answer("Ошибка: пользователь не найден.")
        return
    
    if teacher["role"] not in ["teacher", "admin"] or teacher["status"] != "approved":
        await callback_query.answer("У вас нет прав для выполнения этого действия.")
        return
    
    # Обновляем статус студента
    await db.update_user_status(student_id, "approved")
    
    # Обновляем информацию о учителе группы (если это преподаватель)
    if teacher["role"] == "teacher":
        await db.add_group(student["group_code"], teacher["telegram_id"])
    
    # Уведомляем преподавателя
    await callback_query.answer(f"Студент {student['full_name']} подтвержден!")
    
    # Обновляем список ожидающих подтверждения
    keyboard = await get_pending_students_keyboard()
    
    if keyboard:
        await callback_query.message.edit_text(
            "Список студентов, ожидающих подтверждения регистрации:",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.edit_text("Все заявки обработаны.")
    
    # Отправляем уведомление студенту
    try:
        await callback_query.bot.send_message(
            student_id,
            f"Ваша регистрация подтверждена преподавателем {teacher['full_name']}. "
            f"Теперь вы можете использовать все функции бота!"
        )
    except Exception:
        # Если не удалось отправить сообщение студенту
        pass

# Команда управления группами (для преподавателей)
async def cmd_manage_groups(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    
    if not user or user["role"] not in ["teacher", "admin"] or user["status"] != "approved":
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    # Создаем клавиатуру с действиями
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(
        KeyboardButton("Просмотреть группы"),
        KeyboardButton("Перевести студента"),
        KeyboardButton("Добавить новую группу"),
        KeyboardButton("Отмена")
    )
    
    await message.answer(
        "Выберите действие с группами:",
        reply_markup=keyboard
    )
    
    await GroupManagementStates.choosing_action.set()

# Обработчик выбора действия в управлении группами
async def process_group_action(message: types.Message, state: FSMContext):
    action = message.text.lower()
    
    # Получаем данные пользователя в начале функции
    user = await db.get_user(message.from_user.id)
    
    if action == "отмена":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    if action == "просмотреть группы":
        # Получаем доступные группы
        groups = await db.get_groups()
        
        if not groups:
            await message.answer("В системе нет зарегистрированных групп.", reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return
        
        # Фильтруем группы для преподавателя
        if user["role"] == "teacher":
            groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
            
            if not groups:
                await message.answer("У вас нет закрепленных групп.", reply_markup=types.ReplyKeyboardRemove())
                await state.finish()
                return
        
        # Выводим списки студентов по группам
        for group in groups:
            group_code = group["group_code"]
            students = await db.get_students_by_group(group_code)
            
            response = f"📝 Группа: {group_code}\n\n"
            
            if not students:
                response += "В этой группе нет студентов."
            else:
                for i, student in enumerate(students, 1):
                    response += f"{i}. {student['full_name']}\n"
            
            await message.answer(response)
        
        # Возвращаем клавиатуру пользователя в зависимости от роли
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await message.answer("Списки групп успешно получены.", reply_markup=keyboard)
        await state.finish()
        
    elif action == "перевести студента":
        # Получаем доступные группы для выбора исходной группы
        groups = await db.get_groups()
        
        if not groups:
            await message.answer("В системе нет зарегистрированных групп.", reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return
        
        # Фильтруем группы для преподавателя
        if user["role"] == "teacher":
            groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
            
            if not groups:
                await message.answer("У вас нет закрепленных групп.", reply_markup=types.ReplyKeyboardRemove())
                await state.finish()
                return
        
        # Создаем клавиатуру с группами
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for group in groups:
            keyboard.add(KeyboardButton(group["group_code"]))
        keyboard.add(KeyboardButton("Отмена"))
        
        await message.answer(
            "Выберите группу, из которой нужно перевести студента:",
            reply_markup=keyboard
        )
        
        await GroupManagementStates.selecting_group.set()
        
    elif action == "добавить новую группу":
        # Проверяем права пользователя
        if user["role"] not in ["teacher", "admin"]:
            await message.answer("У вас нет прав для добавления новых групп.")
            return
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(KeyboardButton("Отмена"))
        
        await message.answer(
            "Введите код новой группы (2-10 символов):\n"
            "Например: ИС-21, М-22, ФИЗ-23 и т.д.",
            reply_markup=keyboard
        )
        
        await GroupManagementStates.entering_new_group_code.set()

# Обработчик выбора группы для перевода
async def process_select_group(message: types.Message, state: FSMContext):
    group_code = message.text.strip()
    
    if group_code.lower() == "отмена":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        user = await db.get_user(message.from_user.id)
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    # Получаем список студентов выбранной группы
    students = await db.get_students_by_group(group_code)
    
    if not students:
        await message.answer(f"В группе {group_code} нет студентов.", reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
        return
    
    # Сохраняем выбранную группу
    await state.update_data(source_group=group_code)
    
    # Создаем клавиатуру со студентами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for student in students:
        keyboard.add(KeyboardButton(f"{student['full_name']} ({student['telegram_id']})"))
    keyboard.add(KeyboardButton("Отмена"))
    
    await message.answer(
        f"Выберите студента из группы {group_code} для перевода:",
        reply_markup=keyboard
    )
    
    await GroupManagementStates.selecting_student.set()

# Обработчик выбора студента для перевода
async def process_select_student(message: types.Message, state: FSMContext):
    student_info = message.text.strip()
    
    if student_info.lower() == "отмена":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        user = await db.get_user(message.from_user.id)
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    # Извлекаем Telegram ID студента из текста кнопки
    try:
        student_id = int(student_info.split("(")[1].split(")")[0])
    except (IndexError, ValueError):
        await message.answer("Ошибка при выборе студента. Пожалуйста, выберите студента из списка.")
        return
    
    # Получаем данные о студенте
    student = await db.get_user(student_id)
    
    if not student or student["role"] != "student":
        await message.answer("Ошибка: выбранный пользователь не является студентом.", reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
        return
    
    # Сохраняем ID и имя выбранного студента
    await state.update_data(student_id=student_id, student_name=student["full_name"])
    
    # Получаем список доступных групп для перевода
    user = await db.get_user(message.from_user.id)
    groups = await db.get_groups()
    
    # Фильтруем группы
    if user["role"] == "teacher":
        groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
    
    # Создаем клавиатуру с группами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for group in groups:
        if group["group_code"] != student["group_code"]:  # Исключаем текущую группу студента
            keyboard.add(KeyboardButton(group["group_code"]))
    keyboard.add(KeyboardButton("Отмена"))
    
    await message.answer(
        f"Выберите новую группу для студента {student['full_name']}:",
        reply_markup=keyboard
    )
    
    await GroupManagementStates.selecting_new_group.set()

# Обработчик выбора новой группы
async def process_select_new_group(message: types.Message, state: FSMContext):
    new_group = message.text.strip()
    
    if new_group.lower() == "отмена":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        user = await db.get_user(message.from_user.id)
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=keyboard)
        return
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    student_id = user_data["student_id"]
    student_name = user_data["student_name"]
    source_group = user_data["source_group"]
    
    # Проверяем существование группы
    groups = await db.get_groups()
    group_exists = any(group["group_code"] == new_group for group in groups)
    
    if not group_exists:
        await message.answer(f"Ошибка: группа {new_group} не существует.")
        return
    
    # Сохраняем новую группу
    await state.update_data(new_group=new_group)
    
    # Запрашиваем подтверждение
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton("Подтвердить"), KeyboardButton("Отмена"))
    
    await message.answer(
        f"Вы собираетесь перевести студента {student_name} из группы {source_group} в группу {new_group}.\n\n"
        f"Подтвердите перевод:",
        reply_markup=keyboard
    )
    
    await GroupManagementStates.confirming_transfer.set()

# Обработчик подтверждения перевода
async def process_confirm_transfer(message: types.Message, state: FSMContext):
    confirmation = message.text.lower()
    
    if confirmation != "подтвердить":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        user = await db.get_user(message.from_user.id)
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Перевод отменен.", reply_markup=keyboard)
        return
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    student_id = user_data["student_id"]
    student_name = user_data["student_name"]
    source_group = user_data["source_group"]
    new_group = user_data["new_group"]
    
    # Обновляем группу студента
    await db.update_user_group(student_id, new_group)
    
    # Отправляем уведомление студенту о переводе
    success = await send_group_change_notification(message.bot, student_id, source_group, new_group)
    
    # Получаем клавиатуру в зависимости от роли пользователя
    user = await db.get_user(message.from_user.id)
    if user["role"] == "teacher":
        keyboard = get_teacher_keyboard()
    elif user["role"] == "admin":
        keyboard = get_admin_keyboard()
    else:
        keyboard = None
    
    # Выводим сообщение об успешном переводе
    await message.answer(
        f"Студент {student_name} успешно переведен из группы {source_group} в группу {new_group}.\n"
        f"Уведомление {'отправлено' if success else 'не удалось отправить'} студенту.",
        reply_markup=keyboard
    )
    
    # Завершаем FSM
    await state.finish()

# Обработчик ввода кода новой группы
async def process_new_group_code(message: types.Message, state: FSMContext):
    group_code = message.text.strip()
    
    if group_code.lower() == "отмена":
        # Возвращаем клавиатуру в зависимости от роли пользователя
        user = await db.get_user(message.from_user.id)
        if user["role"] == "teacher":
            keyboard = get_teacher_keyboard()
        elif user["role"] == "admin":
            keyboard = get_admin_keyboard()
        else:
            keyboard = None
            
        await state.finish()
        await message.answer("Добавление группы отменено.", reply_markup=keyboard)
        return
    
    # Проверяем длину кода группы
    if len(group_code) < 2 or len(group_code) > 10:
        await message.answer(
            "Код группы должен быть от 2 до 10 символов. Попробуйте еще раз."
        )
        return
    
    # Проверяем, существует ли уже такая группа
    groups = await db.get_groups()
    if any(group["group_code"] == group_code for group in groups):
        await message.answer(
            f"Группа с кодом {group_code} уже существует. Введите другой код."
        )
        return
    
    # Получаем данные пользователя
    user = await db.get_user(message.from_user.id)
    
    # Добавляем новую группу
    teacher_id = message.from_user.id if user["role"] == "teacher" else None
    await db.add_group(group_code, teacher_id)
    
    # Возвращаем клавиатуру в зависимости от роли пользователя
    if user["role"] == "teacher":
        keyboard = get_teacher_keyboard()
    elif user["role"] == "admin":
        keyboard = get_admin_keyboard()
    else:
        keyboard = None
    
    await message.answer(
        f"Группа {group_code} успешно добавлена!\n"
        f"{'Вы назначены преподавателем этой группы.' if user['role'] == 'teacher' else ''}",
        reply_markup=keyboard
    )
    
    # Завершаем FSM
    await state.finish()

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    dp.register_message_handler(cmd_start, commands=["start"], state="*")
    dp.register_message_handler(process_role_selection, state=RegistrationStates.choose_role)
    dp.register_message_handler(process_fullname, state=RegistrationStates.enter_fullname)
    dp.register_message_handler(process_group_code, state=RegistrationStates.enter_group)
    dp.register_message_handler(process_teacher_code, state=RegistrationStates.enter_teacher_code)
    dp.register_message_handler(process_admin_code, state=RegistrationStates.enter_admin_code)
    dp.register_message_handler(cmd_pending_requests, commands=["pending_requests"])
    dp.register_message_handler(cmd_requests, commands=["requests"])
    dp.register_callback_query_handler(process_approve_button, lambda c: c.data.startswith("approve_"))
    
    # Регистрация обработчиков для управления группами
    dp.register_message_handler(cmd_manage_groups, commands=["manage_groups"])
    dp.register_message_handler(process_group_action, state=GroupManagementStates.choosing_action)
    dp.register_message_handler(process_select_group, state=GroupManagementStates.selecting_group)
    dp.register_message_handler(process_select_student, state=GroupManagementStates.selecting_student)
    dp.register_message_handler(process_select_new_group, state=GroupManagementStates.selecting_new_group)
    dp.register_message_handler(process_confirm_transfer, state=GroupManagementStates.confirming_transfer) 
    dp.register_message_handler(process_new_group_code, state=GroupManagementStates.entering_new_group_code)
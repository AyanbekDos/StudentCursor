# registration.py
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from config import TEACHER_CODE
from localization.kz_text import MESSAGES, BUTTONS, ROLES, REQUEST_MESSAGES, GROUP_MESSAGES, DELETE_PROFILE_MESSAGES
from modules.keyboards import get_student_keyboard, get_teacher_keyboard
from modules.notifications import send_group_change_notification

logger = logging.getLogger(__name__)

# Определение состояний для FSM
class RegistrationStates(StatesGroup):
    choose_role = State()
    enter_fullname = State()
    enter_group = State()
    enter_teacher_code = State()

# Состояния для управления группами
class GroupManagementStates(StatesGroup):
    choosing_action = State()
    selecting_group = State()
    selecting_student = State()
    selecting_new_group = State()
    confirming_transfer = State()
    entering_new_group_code = State()
    selecting_group_to_delete = State()
    confirming_group_deletion = State()

# Состояния для удаления профиля
class DeleteProfileStates(StatesGroup):
    confirming_deletion = State()

# Класс для выбора существующей группы
class ExistingGroupStates(StatesGroup):
    selecting_group = State()

# Клавиатура для выбора роли (только студент и преподаватель)
def get_role_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton(ROLES["student"]))
    keyboard.add(KeyboardButton(ROLES["teacher"]))
    return keyboard

# Обработчик команды /start
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"Команда /start от пользователя {message.from_user.id}")
    user = await db.get_user(message.from_user.id)
    
    if user:
        # Пользователь уже зарегистрирован
        status = user["status"]
        role = user["role"]
        logger.info(f"Пользователь {message.from_user.id} уже зарегистрирован: роль={role}, статус={status}")
        
        if status == "pending":
            await message.answer(MESSAGES["pending_approval"])
        elif status == "approved":
            if role == "student":
                keyboard = get_student_keyboard()
                await message.answer(
                    f"{MESSAGES['welcome']}\n"
                    f"{MESSAGES['student_approved'].format(group_code=user['group_code'])}",
                    reply_markup=keyboard
                )
            elif role == "teacher":
                keyboard = get_teacher_keyboard()
                await message.answer(
                    f"{MESSAGES['welcome']}\n"
                    f"{MESSAGES['teacher_approved']}",
                    reply_markup=keyboard
                )
        elif status == "rejected":
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton(MESSAGES["repeat_registration"]))
            await message.answer(MESSAGES["registration_rejected"], reply_markup=keyboard)
    else:
        logger.info(f"Новый пользователь {message.from_user.id}, начинаем регистрацию")
        # Начинаем регистрацию
        await message.answer(
            f"{MESSAGES['welcome']}\n{MESSAGES['choose_role']}",
            reply_markup=get_role_keyboard()
        )
        await RegistrationStates.choose_role.set()

# Обработчик выбора роли
async def process_role_selection(message: types.Message, state: FSMContext):
    logger.info(f"Выбор роли: {message.text}")
    selected_role = None
    for role_key, role_name in ROLES.items():
        if message.text == role_name and role_key in ["student", "teacher"]:
            selected_role = role_key
            break
    
    if not selected_role:
        logger.warning(f"Неизвестная роль: {message.text}")
        await message.answer(
            MESSAGES["choose_role"],
            reply_markup=get_role_keyboard()
        )
        return
    
    logger.info(f"Выбрана роль: {selected_role}")
    # Сохраняем выбранную роль
    await state.update_data(role=selected_role)
    
    # Запрашиваем ФИО
    await message.answer(MESSAGES["enter_fullname"], reply_markup=types.ReplyKeyboardRemove())
    await RegistrationStates.enter_fullname.set()

# Обработчик ввода ФИО
async def process_fullname(message: types.Message, state: FSMContext):
    fullname = message.text.strip()
    logger.info(f"Введено ФИО: {fullname}")
    
    if len(fullname.split()) < 2:
        logger.warning(f"Некорректное ФИО: {fullname}")
        await message.answer(MESSAGES["fullname_error"])
        return
    
    # Сохраняем ФИО
    await state.update_data(fullname=fullname)
    
    # Получаем данные из состояния
    user_data = await state.get_data()
    role = user_data["role"]
    
    if role == "student":
        # Получаем список существующих групп
        groups = await db.get_groups()
        logger.info(f"Найдено групп: {len(groups) if groups else 0}")
        
        if not groups:
            await message.answer(
                MESSAGES["no_groups"],
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            return
        
        # Показываем список существующих групп для выбора
        keyboard = await get_existing_groups_keyboard()
        await message.answer(
            MESSAGES["select_existing_group"],
            reply_markup=keyboard
        )
        
        # Переходим в состояние выбора существующей группы
        await ExistingGroupStates.selecting_group.set()
        
    elif role == "teacher":
        # Запрашиваем секретный код для преподавателя
        await message.answer(MESSAGES["enter_teacher_code"])
        await RegistrationStates.enter_teacher_code.set()

# Функция для получения клавиатуры с существующими группами
async def get_existing_groups_keyboard():
    groups = await db.get_groups()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    
    # Добавляем кнопки с кодами групп
    for group in groups:
        keyboard.add(KeyboardButton(group["group_code"]))
    
    # Добавляем кнопку отмены
    keyboard.add(KeyboardButton(BUTTONS["cancel"]))
    return keyboard

async def process_existing_group_selection(message: types.Message, state: FSMContext):
    """Обработчик выбора существующей группы из списка"""
    logger.info(f"Выбрана группа: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        logger.info("Отмена выбора группы")
        await state.finish()
        await message.answer(MESSAGES["action_cancelled"], reply_markup=types.ReplyKeyboardRemove())
        return
    
    group_code = message.text.strip().upper()
    
    # Проверяем, существует ли группа
    groups = await db.get_groups()
    group_exists = False
    group_info = None
    
    for group in groups:
        if group["group_code"] == group_code:
            group_exists = True
            group_info = group
            break
    
    if not group_exists:
        logger.warning(f"Группа не найдена: {group_code}")
        keyboard = await get_existing_groups_keyboard()
        await message.answer(
            MESSAGES["group_not_exists"].format(group_code=group_code),
            reply_markup=keyboard
        )
        return
    
    # Получаем данные пользователя
    user_data = await state.get_data()
    
    # Регистрируем студента (статус "pending" - ожидает подтверждения)
    await db.add_user(
        telegram_id=message.from_user.id,
        full_name=user_data["fullname"],
        role=user_data["role"],
        group_code=group_code
    )
    
    logger.info(f"Студент зарегистрирован: {user_data['fullname']} в группе {group_code}")
    
    # Уведомляем пользователя
    await message.answer(
        MESSAGES["registration_sent"].format(
            fullname=user_data["fullname"],
            group_code=group_code
        ),
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Отправляем уведомление преподавателю, если он закреплен за группой
    if group_info and group_info["teacher_telegram_id"]:
        teacher_id = int(group_info["teacher_telegram_id"])
        teacher = await db.get_user(teacher_id)
        
        if teacher:
            logger.info(f"Отправляем уведомление преподавателю {teacher_id}")
            # Создаем клавиатуру с кнопкой для просмотра заявок
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                "Өтініштерді қарау",
                callback_data="view_requests"
            ))
            
            # Отправляем уведомление преподавателю используя существующий бот
            try:
                await message.bot.send_message(
                    chat_id=teacher_id,
                    text=f"{group_code} тобына жаңа тіркелу өтініші!\n"
                         f"Студент: {user_data['fullname']}\n"
                         f"Өтініштерді растау немесе қабылдамау үшін /requests командасын пайдаланыңыз",
                    reply_markup=keyboard
                )
                logger.info("Уведомление преподавателю отправлено успешно")
            except Exception as e:
                logger.error(f"Оқытушыға хабарлама жіберу сәтсіз болды: {e}")
    
    # Сбрасываем состояние
    await state.finish()

# Обработчик ввода кода преподавателя
async def process_teacher_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    logger.info(f"Введен код преподавателя: {code}")
    
    if code != TEACHER_CODE:
        logger.warning("Неверный код преподавателя")
        await message.answer(MESSAGES["invalid_teacher_code"])
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
    
    logger.info(f"Преподаватель зарегистрирован: {user_data['fullname']}")
    
    # Уведомляем пользователя
    await message.answer(
        f"{MESSAGES['registration_success']}\n{MESSAGES['teacher_approved']}"
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
        # Создаем кнопки для каждого студента
        approve_button = InlineKeyboardButton(
            f"✅ {student['full_name']} - {student['group_code']}",
            callback_data=f"approve_{student['telegram_id']}_accept"
        )
        reject_button = InlineKeyboardButton(
            f"❌ {student['full_name']} - {student['group_code']}",
            callback_data=f"approve_{student['telegram_id']}_reject"
        )
        keyboard.add(approve_button)
        keyboard.add(reject_button)
    
    return keyboard

# Обработчик команды для просмотра заявок (для преподавателя)
async def cmd_pending_requests(message: types.Message):
    logger.info(f"Запрос заявок от пользователя {message.from_user.id}")
    user = await db.get_user(message.from_user.id)
    
    # Проверяем, что пользователь - преподаватель
    if not user or user['role'] != 'teacher':
        logger.warning(f"Пользователь {message.from_user.id} не является преподавателем")
        await message.answer(MESSAGES["teacher_only"])
        return
    
    # Получаем список заявок на подтверждение
    keyboard = await get_pending_students_keyboard()
    
    if keyboard and keyboard.inline_keyboard:
        logger.info("Отправляем список заявок")
        await message.answer(REQUEST_MESSAGES["pending_requests_list"], reply_markup=keyboard)
    else:
        logger.info("Нет заявок для отображения")
        keyboard = get_teacher_keyboard()
        await message.answer(REQUEST_MESSAGES["no_pending_requests"], reply_markup=keyboard)

# Обработчик кнопки "Заявки"
async def cmd_requests(message: types.Message, state: FSMContext = None):
    """Обрабатывает нажатие на кнопку "Заявки" или команду /requests"""
    await cmd_pending_requests(message)

# Обработчик кнопки "Просмотреть заявки"
async def process_view_requests_button(callback_query: types.CallbackQuery):
    """Обработчик кнопки 'Просмотреть заявки'"""
    logger.info(f"Нажата кнопка 'Просмотреть заявки' пользователем {callback_query.from_user.id}")
    user = await db.get_user(callback_query.from_user.id)
    
    if not user or user["role"] != "teacher":
        await callback_query.answer("Бұл функцияға қолжетімділігіңіз жоқ.")
        return
    
    # Отвечаем на callback, чтобы убрать индикатор загрузки
    await callback_query.answer()
    
    # Получаем список заявок
    pending_students = await db.get_pending_students()
    
    if not pending_students:
        await callback_query.message.answer("Растауды күтетін өтініштер жоқ.")
        return
    
    # Создаем клавиатуру с заявками
    keyboard = await get_pending_students_keyboard()
    
    if keyboard and keyboard.inline_keyboard:
        await callback_query.message.answer(
            REQUEST_MESSAGES["pending_requests_list"],
            reply_markup=keyboard
        )

# Обработчик нажатия на кнопку подтверждения регистрации
async def process_approve_button(callback_query: types.CallbackQuery):
    logger.info(f"Нажата кнопка подтверждения: {callback_query.data}")
    # Извлекаем ID студента и действие из callback_data
    callback_data_parts = callback_query.data.split("_")
    student_id = int(callback_data_parts[1])
    action = callback_data_parts[2] if len(callback_data_parts) > 2 else "accept"
    
    # Получаем данные студента и учителя
    student = await db.get_user(student_id)
    teacher = await db.get_user(callback_query.from_user.id)
    
    if not student or not teacher:
        await callback_query.answer(REQUEST_MESSAGES["user_not_found"])
        return
    
    if teacher["role"] != "teacher" or teacher["status"] != "approved":
        await callback_query.answer(REQUEST_MESSAGES["no_permission"])
        return
    
    if action == "accept":
        logger.info(f"Подтверждение заявки студента {student_id}")
        # Подтверждаем заявку
        await db.update_user_status(student_id, "approved")
        
        # Обновляем информацию о учителе группы
        await db.add_group(student["group_code"], teacher["telegram_id"])
        
        # Уведомляем преподавателя
        await callback_query.answer(REQUEST_MESSAGES["student_approved"].format(student_name=student['full_name']))
        
        # Отправляем уведомление студенту
        try:
            await callback_query.bot.send_message(
                student_id,
                REQUEST_MESSAGES["approval_notification"].format(teacher_name=teacher['full_name'])
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления студенту: {e}")
            
    elif action == "reject":
        logger.info(f"Отклонение заявки студента {student_id}")
        # Отклоняем заявку
        await db.update_user_status(student_id, "rejected")
        
        # Уведомляем преподавателя
        await callback_query.answer(REQUEST_MESSAGES["student_rejected"].format(student_name=student['full_name']))
        
        # Отправляем уведомление студенту
        try:
            await callback_query.bot.send_message(
                student_id,
                REQUEST_MESSAGES["rejection_notification"].format(
                    group_code=student['group_code'],
                    teacher_name=teacher['full_name']
                )
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления студенту: {e}")
    
    # Обновляем список ожидающих подтверждения
    keyboard = await get_pending_students_keyboard()
    if keyboard and keyboard.inline_keyboard:
        await callback_query.message.edit_text(
            REQUEST_MESSAGES["pending_requests_list"],
            reply_markup=keyboard
        )
    else:
        await callback_query.message.edit_text(REQUEST_MESSAGES["all_requests_processed"])

# Команда управления группами (для преподавателей)
async def cmd_manage_groups(message: types.Message, state: FSMContext):
    logger.info(f"Команда управления группами от пользователя {message.from_user.id}")
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "teacher" or user["status"] != "approved":
        logger.warning(f"Пользователь {message.from_user.id} не имеет доступа к управлению группами")
        await message.answer(MESSAGES["no_access"])
        return
    
    # Создаем клавиатуру с действиями
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(
        KeyboardButton(BUTTONS["view_groups"]),
        KeyboardButton(BUTTONS["transfer_student"]),
        KeyboardButton(BUTTONS["add_new_group"]),
        KeyboardButton(BUTTONS["delete_group"]),
        KeyboardButton(BUTTONS["cancel"])
    )
    
    await message.answer(
        MESSAGES["choose_action"],
        reply_markup=keyboard
    )
    await GroupManagementStates.choosing_action.set()

# ДОБАВЛЯЕМ ОБРАБОТЧИК ВЫБОРА ДЕЙСТВИЯ ДЛЯ УПРАВЛЕНИЯ ГРУППАМИ
async def process_group_action(message: types.Message, state: FSMContext):
    logger.info(f"Выбрано действие управления группами: {message.text}")
    action = message.text.lower()
    user = await db.get_user(message.from_user.id)
    
    if action == BUTTONS["cancel"].lower():
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    if action == BUTTONS["view_groups"].lower():
        logger.info("Просмотр групп")
        # Получаем доступные группы
        groups = await db.get_groups()
        groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
        
        if not groups:
            await message.answer(GROUP_MESSAGES["no_assigned_groups"], reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return
        
        # Выводим списки студентов по группам
        for group in groups:
            group_code = group["group_code"]
            students = await db.get_students_by_group(group_code)
            response = GROUP_MESSAGES["group_title"].format(group_code=group_code) + "\n\n"
            
            if not students:
                response += GROUP_MESSAGES["no_students_in_group"]
            else:
                for i, student in enumerate(students, 1):
                    response += f"{i}. {student['full_name']}\n"
            
            await message.answer(response)
        
        keyboard = get_teacher_keyboard()
        await message.answer(GROUP_MESSAGES["groups_retrieved"], reply_markup=keyboard)
        await state.finish()
        
    elif action == BUTTONS["transfer_student"].lower():
        logger.info("Перевод студента")
        # Получаем доступные группы для выбора исходной группы
        groups = await db.get_groups()
        groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
        
        if not groups:
            await message.answer(GROUP_MESSAGES["no_assigned_groups"], reply_markup=types.ReplyKeyboardRemove())
            await state.finish()
            return
        
        # Создаем клавиатуру с группами
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for group in groups:
            keyboard.add(KeyboardButton(group["group_code"]))
        keyboard.add(KeyboardButton(BUTTONS["cancel"]))
        
        await message.answer(
            GROUP_MESSAGES["choose_source_group"],
            reply_markup=keyboard
        )
        await GroupManagementStates.selecting_group.set()
        
    elif action == BUTTONS["add_new_group"].lower():
        logger.info("Добавление новой группы")
        # Создаем клавиатуру с кнопкой отмены
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(KeyboardButton(BUTTONS["cancel"]))
        
        await message.answer(
            GROUP_MESSAGES["enter_new_group_code"],
            reply_markup=keyboard
        )
        await GroupManagementStates.entering_new_group_code.set()

    elif action == BUTTONS["delete_group"].lower():
        logger.info("Удаление группы")
        # Получаем доступные группы для удаления
        groups = await db.get_groups()
        teacher_groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
        
        if not teacher_groups:
            keyboard = get_teacher_keyboard()
            await message.answer(
                GROUP_MESSAGES["no_groups_to_delete"],
                reply_markup=keyboard
            )
            await state.finish()
            return
        
        # Создаем клавиатуру с группами для удаления
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for group in teacher_groups:
            keyboard.add(KeyboardButton(group["group_code"]))
        keyboard.add(KeyboardButton(BUTTONS["cancel"]))
        
        await message.answer(
            GROUP_MESSAGES["choose_group_delete"],
            reply_markup=keyboard
        )
        await GroupManagementStates.selecting_group_to_delete.set()

# ДОБАВЛЯЕМ ОБРАБОТЧИК ДЛЯ ВВОДА КОДА НОВОЙ ГРУППЫ
async def process_new_group_code(message: types.Message, state: FSMContext):
    logger.info(f"Введен код новой группы: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["group_adding_cancelled"], reply_markup=keyboard)
        return
    
    group_code = message.text.strip().upper()
    
    # Проверяем длину кода группы
    if len(group_code) < 2 or len(group_code) > 10:
        await message.answer(GROUP_MESSAGES["group_code_length"])
        return
    
    # Проверяем, не существует ли уже такая группа
    existing_groups = await db.get_groups()
    for group in existing_groups:
        if group["group_code"] == group_code:
            await message.answer(GROUP_MESSAGES["group_exists"].format(group_code=group_code))
            return
    
    # Добавляем новую группу
    user = await db.get_user(message.from_user.id)
    await db.add_group(group_code, user["telegram_id"])
    
    keyboard = get_teacher_keyboard()
    await message.answer(
        GROUP_MESSAGES["group_added"].format(group_code=group_code, is_teacher=True),
        reply_markup=keyboard
    )
    await state.finish()

async def process_select_source_group(message: types.Message, state: FSMContext):
    """Обработчик выбора исходной группы для перевода студента"""
    logger.info(f"Выбрана исходная группа для перевода: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(MESSAGES["action_cancelled"], reply_markup=keyboard)
        return
    
    group_code = message.text.strip()
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer(f"Топ {group_code} табылмады. Тізімнен топты таңдаңыз.")
        return
    
    # Получаем студентов выбранной группы
    students = await db.get_students_by_group(group_code)
    
    if not students:
        keyboard = get_teacher_keyboard()
        await message.answer(
            GROUP_MESSAGES["no_students_transfer"].format(group_code=group_code),
            reply_markup=keyboard
        )
        await state.finish()
        return
    
    # Создаем клавиатуру со студентами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for student in students:
        keyboard.add(KeyboardButton(student["full_name"]))
    keyboard.add(KeyboardButton(BUTTONS["cancel"]))
    
    # Сохраняем выбранную группу
    await state.update_data(source_group=group_code)
    
    await message.answer(
        GROUP_MESSAGES["choose_student_transfer"].format(group_code=group_code),
        reply_markup=keyboard
    )
    await GroupManagementStates.selecting_student.set()

# Обработчик выбора студента для перевода
async def process_select_student_transfer(message: types.Message, state: FSMContext):
    """Обработчик выбора студента для перевода"""
    logger.info(f"Выбран студент для перевода: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["transfer_cancelled"], reply_markup=keyboard)
        return
    
    selected_student_name = message.text.strip()
    data = await state.get_data()
    source_group = data.get('source_group')
    
    # Получаем список студентов из исходной группы
    students = await db.get_students_by_group(source_group)
    
    # Ищем студента по имени
    selected_student = None
    for student in students:
        if student['full_name'] == selected_student_name:
            selected_student = student
            break
    
    if not selected_student:
        await message.answer("Студент табылмады. Тізімнен таңдаңыз.")
        return
    
    # Сохраняем только нужные данные, а не полный объект
    await state.update_data(
        selected_student_id=selected_student['telegram_id'],
        selected_student_name=selected_student['full_name']
    )
    
    # Получаем список всех групп для выбора новой группы
    groups = await db.get_groups()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for group in groups:
        # Исключаем исходную группу из списка
        if group["group_code"] != source_group:
            keyboard.add(KeyboardButton(group["group_code"]))
    keyboard.add(KeyboardButton(BUTTONS["cancel"]))
    
    await message.answer(
        GROUP_MESSAGES["choose_target_group"].format(student_name=selected_student_name),
        reply_markup=keyboard
    )
    await GroupManagementStates.selecting_new_group.set()

# Обработчик выбора новой группы для студента
async def process_select_new_group(message: types.Message, state: FSMContext):
    """Обработчик выбора новой группы для перевода студента"""
    logger.info(f"Выбрана новая группа: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["transfer_cancelled"], reply_markup=keyboard)
        return
    
    new_group_code = message.text.strip()
    data = await state.get_data()
    
    # Используем правильные имена переменных
    selected_student_id = data.get('selected_student_id')
    selected_student_name = data.get('selected_student_name')
    source_group = data.get('source_group')
    
    # Проверяем существование новой группы
    groups = await db.get_groups()
    if not any(group["group_code"] == new_group_code for group in groups):
        await message.answer("Топ табылмады. Тізімнен таңдаңыз.")
        return
    
    # Показываем подтверждение перевода
    await message.answer(
        GROUP_MESSAGES["confirm_transfer"].format(
            student_name=selected_student_name,
            source_group=source_group,
            target_group=new_group_code
        ),
        reply_markup=get_confirm_keyboard()
    )
    
    # Сохраняем новую группу
    await state.update_data(new_group_code=new_group_code)
    await GroupManagementStates.confirming_transfer.set()

# Обработчик подтверждения перевода студента
async def process_confirm_transfer(message: types.Message, state: FSMContext):
    """Обработчик подтверждения перевода студента"""
    logger.info(f"Подтверждение перевода: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["transfer_cancelled"], reply_markup=keyboard)
        return
    
    if message.text.strip() == BUTTONS["confirm"]:
        data = await state.get_data()
        
        # Используем правильные имена переменных
        selected_student_id = data.get('selected_student_id')
        selected_student_name = data.get('selected_student_name')
        source_group = data.get('source_group')
        new_group_code = data.get('new_group_code')
        
        # Выполняем перевод студента в базе данных
        await db.update_user_group(selected_student_id, new_group_code)
        
        keyboard = get_teacher_keyboard()
        await message.answer(
            GROUP_MESSAGES["transfer_success"].format(
                student_name=selected_student_name,
                source_group=source_group,
                target_group=new_group_code
            ),
            reply_markup=keyboard
        )
        
        # Отправляем уведомление студенту о переводе
        try:
            notification_sent = await send_group_change_notification(
                message.bot, 
                selected_student_id, 
                source_group, 
                new_group_code
            )
            if not notification_sent:
                logger.warning(f"Не удалось отправить уведомление студенту {selected_student_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления студенту: {e}")
        
        await state.finish()
    else:
        # Неправильный ответ
        await message.answer(
            "Растау немесе болдырмау батырмасын басыңыз:",
            reply_markup=get_confirm_keyboard()
        )

# Функция для создания клавиатуры подтверждения
def get_confirm_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton(BUTTONS["confirm"]), KeyboardButton(BUTTONS["cancel"]))
    return keyboard

# Функция для удаления профиля
async def cmd_delete_profile(message: types.Message, state: FSMContext):
    logger.info(f"Запрос удаления профиля от пользователя {message.from_user.id}")
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer(DELETE_PROFILE_MESSAGES["not_registered"])
        return
    
    if user["role"] != "student":
        await message.answer(DELETE_PROFILE_MESSAGES["students_only"])
        return
    
    # Создаем клавиатуру с кнопками подтверждения/отмены
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton(DELETE_PROFILE_MESSAGES["confirm_delete"]))
    keyboard.add(KeyboardButton(BUTTONS["cancel"]))
    
    await message.answer(
        DELETE_PROFILE_MESSAGES["confirm_deletion"],
        reply_markup=keyboard
    )
    await DeleteProfileStates.confirming_deletion.set()

# Обработчик подтверждения удаления профиля
async def process_delete_profile_confirmation(message: types.Message, state: FSMContext):
    logger.info(f"Подтверждение удаления профиля: {message.text}")
    
    if message.text == DELETE_PROFILE_MESSAGES["confirm_delete"]:
        # Удаляем профиль пользователя
        await db.delete_user(message.from_user.id)
        await state.finish()
        
        await message.answer(
            DELETE_PROFILE_MESSAGES["profile_deleted"],
            reply_markup=types.ReplyKeyboardRemove()
        )
    elif message.text == BUTTONS["cancel"]:
        keyboard = get_student_keyboard()
        await message.answer(DELETE_PROFILE_MESSAGES["deletion_cancelled"], reply_markup=keyboard)
        await state.finish()
    else:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton(DELETE_PROFILE_MESSAGES["confirm_delete"]))
        keyboard.add(KeyboardButton(BUTTONS["cancel"]))
        
        await message.answer(
            DELETE_PROFILE_MESSAGES["choose_option"],
            reply_markup=keyboard
        )

# Обработчик кнопки "Повторная регистрация"
async def process_reregister(message: types.Message, state: FSMContext):
    if message.text != MESSAGES["repeat_registration"]:
        return
    
    user = await db.get_user(message.from_user.id)
    if not user or user["status"] != "rejected":
        return
    
    # Удаляем пользователя из базы данных
    await db.delete_user(message.from_user.id)
    
    # Начинаем регистрацию заново
    await message.answer(
        f"{MESSAGES['welcome']}\n{MESSAGES['choose_role']}",
        reply_markup=get_role_keyboard()
    )
    await RegistrationStates.choose_role.set()

# Обработчик выбора группы для удаления
async def process_select_group_to_delete(message: types.Message, state: FSMContext):
    """Обработчик выбора группы для удаления"""
    logger.info(f"Выбрана группа для удаления: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["group_deletion_cancelled"], reply_markup=keyboard)
        return
    
    group_code = message.text.strip()
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer("Топ табылмады. Тізімнен таңдаңыз.")
        return
    
    # Проверяем, есть ли студенты в группе
    students = await db.get_students_by_group(group_code)
    
    if students:
        # В группе есть студенты - нельзя удалить
        students_list = "\n".join([f"• {student['full_name']}" for student in students])
        
        keyboard = get_teacher_keyboard()
        await message.answer(
            GROUP_MESSAGES["group_has_students"].format(students_list=students_list),
            reply_markup=keyboard
        )
        await state.finish()
        return
    
    # Группа пустая - можно удалить
    await message.answer(
        GROUP_MESSAGES["confirm_group_deletion"].format(group_code=group_code),
        reply_markup=get_confirm_keyboard()
    )
    
    # Сохраняем код группы для удаления
    await state.update_data(group_to_delete=group_code)
    await GroupManagementStates.confirming_group_deletion.set()

# Обработчик подтверждения удаления группы
async def process_confirm_group_deletion(message: types.Message, state: FSMContext):
    """Обработчик подтверждения удаления группы"""
    logger.info(f"Подтверждение удаления группы: {message.text}")
    
    if message.text.strip() == BUTTONS["cancel"]:
        keyboard = get_teacher_keyboard()
        await state.finish()
        await message.answer(GROUP_MESSAGES["group_deletion_cancelled"], reply_markup=keyboard)
        return
    
    if message.text.strip() == BUTTONS["confirm"]:
        data = await state.get_data()
        group_code = data.get('group_to_delete')
        
        # Удаляем группу из базы данных
        await db.delete_group(group_code)
        
        keyboard = get_teacher_keyboard()
        await message.answer(
            GROUP_MESSAGES["group_deleted"].format(group_code=group_code),
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
    logger.info("Регистрация обработчиков registration.py")
    
    dp.register_message_handler(cmd_start, commands=["start"], state="*")
    dp.register_message_handler(process_role_selection, state=RegistrationStates.choose_role)
    dp.register_message_handler(process_fullname, state=RegistrationStates.enter_fullname)
    dp.register_message_handler(process_teacher_code, state=RegistrationStates.enter_teacher_code)
    dp.register_message_handler(cmd_pending_requests, commands=["pending_requests"])
    dp.register_message_handler(cmd_requests, commands=["requests"])
    dp.register_message_handler(process_reregister, lambda message: message.text == MESSAGES["repeat_registration"], state="*")
    
    # Обработчики для inline кнопок
    dp.register_callback_query_handler(
        process_view_requests_button, 
        lambda c: c.data == "view_requests"
    )
    dp.register_callback_query_handler(
        process_approve_button, 
        lambda c: c.data.startswith("approve_")
    )
    
    # Регистрация обработчиков для управления группами
    dp.register_message_handler(cmd_manage_groups, commands=["manage_groups"])
    dp.register_message_handler(process_group_action, state=GroupManagementStates.choosing_action)
    dp.register_message_handler(process_new_group_code, state=GroupManagementStates.entering_new_group_code)
    dp.register_message_handler(process_select_source_group, state=GroupManagementStates.selecting_group)
    
    # Обработчики для перевода студентов
    dp.register_message_handler(process_select_student_transfer, state=GroupManagementStates.selecting_student)
    dp.register_message_handler(process_select_new_group, state=GroupManagementStates.selecting_new_group)
    dp.register_message_handler(process_confirm_transfer, state=GroupManagementStates.confirming_transfer)
    
    # Регистрация обработчиков для выбора существующей группы
    dp.register_message_handler(process_existing_group_selection, state=ExistingGroupStates.selecting_group)
    
    # Регистрация обработчиков для удаления профиля
    dp.register_message_handler(cmd_delete_profile, commands=["delete_profile"])
    dp.register_message_handler(process_delete_profile_confirmation, state=DeleteProfileStates.confirming_deletion)
    
    # Добавляем новые обработчики для удаления групп
    dp.register_message_handler(process_select_group_to_delete, state=GroupManagementStates.selecting_group_to_delete)
    dp.register_message_handler(process_confirm_group_deletion, state=GroupManagementStates.confirming_group_deletion)
    
    logger.info("Все обработчики registration.py зарегистрированы")

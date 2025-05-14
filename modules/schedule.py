from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite

from database.db import db
from config import WEEKDAYS, SUBJECTS
from modules.notifications import send_schedule_notification

# Определение состояний для FSM
class ScheduleStates(StatesGroup):
    waiting_for_action = State()
    selecting_group = State()  # Новое состояние для выбора группы
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
    keyboard.row(KeyboardButton("Посмотреть расписание"))
    keyboard.row(KeyboardButton("Добавить занятие"), KeyboardButton("Редактировать расписание"))
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Клавиатура для выбора дня недели
def get_weekday_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [KeyboardButton(day) for day in WEEKDAYS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Клавиатура для выбора предмета
def get_subject_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(subject) for subject in SUBJECTS]
    keyboard.add(*buttons)
    keyboard.row(KeyboardButton("Отмена"))
    return keyboard

# Клавиатура для подтверждения изменений
def get_confirm_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton("Подтвердить"), KeyboardButton("Отмена"))
    return keyboard

# Функция для форматирования расписания
def format_schedule(schedule_items):
    if not schedule_items:
        return "Расписание не найдено"
    
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
    result = "📚 РАСПИСАНИЕ:\n\n"
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
    user = await db.get_user(message.from_user.id)
    
    if not user or user["status"] != "approved":
        await message.answer("Вы не зарегистрированы в системе или ваша заявка еще не подтверждена.")
        return
    
    if user["role"] == "student":
        # Для студента просто показываем расписание его группы
        group_code = user["group_code"]
        schedule_items = await db.get_schedule(group_code)
        
        if not schedule_items:
            await message.answer(f"Расписание для группы {group_code} еще не создано.")
        else:
            await message.answer(format_schedule(schedule_items))
    
    elif user["role"] in ["teacher", "admin"]:
        # Для преподавателя показываем меню действий с расписанием
        await message.answer(
            "Выберите действие с расписанием:",
            reply_markup=get_schedule_actions_keyboard()
        )
        await ScheduleStates.waiting_for_action.set()

# Обработчик выбора действия с расписанием
async def process_schedule_action(message: types.Message, state: FSMContext):
    action = message.text.lower()
    
    if action == "отмена":
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
    
    # Сохраняем выбранное действие
    await state.update_data(action=action)
    
    user = await db.get_user(message.from_user.id)
    
    # Получаем список групп в зависимости от роли
    if user["role"] == "teacher":
        # Получаем группы преподавателя
        groups = await db.get_groups()
        available_groups = [group for group in groups if group["teacher_telegram_id"] == message.from_user.id]
        
        if not available_groups:
            await message.answer(
                "У вас нет закрепленных групп. Подтвердите хотя бы одного студента или добавьте новую группу.", 
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            return
    else:  # Для админа
        # Получаем все группы
        groups = await db.get_groups()
        available_groups = groups
        
        if not available_groups:
            await message.answer(
                "В системе нет ни одной группы.", 
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            return
    
    # Создаем клавиатуру с группами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for group in available_groups:
        keyboard.add(KeyboardButton(group["group_code"]))
    keyboard.add(KeyboardButton("Отмена"))
    
    await message.answer(
        "Выберите группу для работы с расписанием:",
        reply_markup=keyboard
    )
    
    await ScheduleStates.selecting_group.set()

# Обработчик выбора группы для работы с расписанием
async def process_select_group(message: types.Message, state: FSMContext):
    group_code = message.text.strip()
    
    if group_code.lower() == "отмена":
        await state.finish()
        await message.answer("Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    # Проверяем существование группы
    groups = await db.get_groups()
    if not any(group["group_code"] == group_code for group in groups):
        await message.answer(f"Группа {group_code} не найдена. Пожалуйста, выберите группу из списка.")
        return
    
    # Сохраняем выбранную группу
    await state.update_data(group_code=group_code)
    
    # Получаем выбранное действие
    user_data = await state.get_data()
    action = user_data.get("action")
    
    if action == "посмотреть расписание":
        schedule_items = await db.get_schedule(group_code)
        await message.answer(
            f"Расписание для группы {group_code}:\n\n{format_schedule(schedule_items)}",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.finish()
    
    elif action == "добавить занятие":
        await message.answer(
            "Выберите день недели для нового занятия:",
            reply_markup=get_weekday_keyboard()
        )
        await ScheduleStates.add_schedule_weekday.set()
    
    elif action == "редактировать расписание":
        schedule_items = await db.get_schedule(group_code)
        
        if not schedule_items:
            await message.answer(
                f"Расписание для группы {group_code} еще не создано.", 
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
            "Выберите занятие для редактирования:",
            reply_markup=keyboard
        )
        await ScheduleStates.edit_schedule_item.set()

# Обработчик выбора дня недели для нового занятия
async def process_add_schedule_weekday(message: types.Message, state: FSMContext):
    weekday = message.text
    
    if weekday.lower() == "отмена":
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
    
    if weekday not in WEEKDAYS:
        await message.answer("Пожалуйста, выберите день недели, используя кнопки ниже:")
        return
    
    # Сохраняем выбранный день недели
    await state.update_data(weekday=weekday)
    
    # Запрашиваем время занятия
    await message.answer(
        "Введите время занятия в формате ЧЧ:ММ (например, 09:30):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await ScheduleStates.add_schedule_time.set()

# Обработчик ввода времени для нового занятия
async def process_add_schedule_time(message: types.Message, state: FSMContext):
    time = message.text.strip()
    
    if time.lower() == "отмена":
        await state.finish()
        await message.answer("Действие отменено.")
        return
    
    # Простая проверка формата времени
    if ":" not in time or len(time) < 4:
        await message.answer("Пожалуйста, введите время в формате ЧЧ:ММ (например, 09:30):")
        return
    
    # Сохраняем время
    await state.update_data(time=time)
    
    # Запрашиваем предмет
    await message.answer(
        "Выберите предмет:",
        reply_markup=get_subject_keyboard()
    )
    await ScheduleStates.add_schedule_subject.set()

# Обработчик выбора предмета для нового занятия
async def process_add_schedule_subject(message: types.Message, state: FSMContext):
    subject = message.text
    
    if subject.lower() == "отмена":
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
    
    if subject not in SUBJECTS:
        await message.answer("Пожалуйста, выберите предмет из списка:")
        return
    
    # Сохраняем предмет
    await state.update_data(subject=subject)
    
    # Получаем все данные, введенные пользователем
    user_data = await state.get_data()
    weekday = user_data["weekday"]
    time = user_data["time"]
    group_code = user_data["group_code"]
    
    # Запрашиваем подтверждение
    await message.answer(
        f"Вы собираетесь добавить занятие:\n"
        f"Группа: {group_code}\n"
        f"День: {weekday}\n"
        f"Время: {time}\n"
        f"Предмет: {subject}\n\n"
        f"Подтвердите добавление:",
        reply_markup=get_confirm_keyboard()
    )
    await ScheduleStates.confirm_schedule_change.set()

# Обработчик подтверждения изменений в расписании
async def process_confirm_schedule_change(message: types.Message, state: FSMContext):
    confirmation = message.text.lower()
    
    if confirmation != "подтвердить":
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
    
    # Получаем все данные, введенные пользователем
    user_data = await state.get_data()
    weekday = user_data["weekday"]
    time = user_data["time"]
    subject = user_data["subject"]
    group_code = user_data["group_code"]
    
    # Добавляем занятие в расписание
    schedule_id = await db.add_schedule_item(group_code, weekday, time, subject)
    
    # Отправляем уведомление студентам группы
    students_notified = await send_schedule_notification(
        message.bot, group_code, "add", weekday, time, subject
    )
    
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
    
    # Выводим сообщение об успешном добавлении
    await message.answer(
        f"Занятие успешно добавлено в расписание группы {group_code}.\n"
        f"Уведомления отправлены {students_notified} студентам.",
        reply_markup=keyboard
    )
    
    # Завершаем FSM
    await state.finish()

# Обработчик выбора занятия для редактирования
async def process_edit_schedule_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID занятия из callback_data
    schedule_id = int(callback_query.data.split("_")[2])
    
    # Сохраняем ID занятия в FSM
    await state.update_data(schedule_id=schedule_id)
    
    await callback_query.answer()
    
    # Запрашиваем новый день недели
    await callback_query.message.answer(
        "Выберите новый день недели для занятия:",
        reply_markup=get_weekday_keyboard()
    )
    await ScheduleStates.edit_schedule_weekday.set()

# Обработчик выбора нового дня недели при редактировании
async def process_edit_schedule_weekday(message: types.Message, state: FSMContext):
    weekday = message.text
    
    if weekday.lower() == "отмена":
        await state.finish()
        await message.answer("Редактирование отменено.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    if weekday not in WEEKDAYS:
        await message.answer("Пожалуйста, выберите день недели, используя кнопки ниже:")
        return
    
    # Сохраняем новый день недели
    await state.update_data(weekday=weekday)
    
    # Запрашиваем новое время занятия
    await message.answer(
        "Введите новое время занятия в формате ЧЧ:ММ (например, 09:30):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await ScheduleStates.edit_schedule_time.set()

# Обработчик ввода нового времени при редактировании
async def process_edit_schedule_time(message: types.Message, state: FSMContext):
    time = message.text.strip()
    
    if time.lower() == "отмена":
        await state.finish()
        await message.answer("Редактирование отменено.")
        return
    
    # Проверка формата времени
    if ":" not in time or len(time) < 4:
        await message.answer("Пожалуйста, введите время в формате ЧЧ:ММ (например, 09:30):")
        return
    
    # Сохраняем новое время
    await state.update_data(time=time)
    
    # Запрашиваем новый предмет
    await message.answer(
        "Выберите новый предмет:",
        reply_markup=get_subject_keyboard()
    )
    await ScheduleStates.edit_schedule_subject.set()

# Обработчик выбора нового предмета при редактировании
async def process_edit_schedule_subject(message: types.Message, state: FSMContext):
    subject = message.text
    
    if subject.lower() == "отмена":
        await state.finish()
        await message.answer("Редактирование отменено.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    if subject not in SUBJECTS:
        await message.answer("Пожалуйста, выберите предмет из списка:")
        return
    
    # Сохраняем новый предмет
    await state.update_data(subject=subject)
    
    # Получаем все данные для редактирования
    user_data = await state.get_data()
    schedule_id = user_data["schedule_id"]
    weekday = user_data["weekday"]
    time = user_data["time"]
    
    # Получаем информацию о редактируемом элементе расписания
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM schedule WHERE id = ?", (schedule_id,)
        ) as cursor:
            schedule_item = await cursor.fetchone()
            
    if not schedule_item:
        await message.answer("Ошибка: занятие не найдено.", reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
        return
    
    group_code = schedule_item["group_code"]
    await state.update_data(group_code=group_code)
    
    # Запрашиваем подтверждение
    await message.answer(
        f"Вы собираетесь изменить занятие для группы {group_code}:\n\n"
        f"Было: {schedule_item['weekday']}, {schedule_item['time']} - {schedule_item['subject']}\n\n"
        f"Станет: {weekday}, {time} - {subject}\n\n"
        f"Подтвердите изменение:",
        reply_markup=get_confirm_keyboard()
    )
    await ScheduleStates.confirm_schedule_change.set()

# Обработчик подтверждения редактирования
async def process_confirm_edit(message: types.Message, state: FSMContext):
    confirmation = message.text.lower()
    
    if confirmation != "подтвердить":
        await state.finish()
        await message.answer("Редактирование отменено.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    # Получаем все данные для редактирования
    user_data = await state.get_data()
    schedule_id = user_data["schedule_id"]
    weekday = user_data["weekday"]
    time = user_data["time"]
    subject = user_data["subject"]
    group_code = user_data["group_code"]
    
    # Обновляем элемент расписания
    success = await db.update_schedule_item(schedule_id, weekday, time, subject)
    
    if not success:
        await message.answer(
            "Ошибка при обновлении расписания.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.finish()
        return
    
    # Отправляем уведомление студентам группы
    students_notified = await send_schedule_notification(
        message.bot, group_code, "update", weekday, time, subject
    )
    
    # Выводим сообщение об успешном обновлении
    await message.answer(
        f"Расписание группы {group_code} успешно обновлено.\n"
        f"Уведомления отправлены {students_notified} студентам.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Завершаем FSM
    await state.finish()

# Обработчик для удаления элемента расписания
async def process_delete_schedule_callback(callback_query: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID занятия из callback_data
    schedule_id = int(callback_query.data.split("_")[2])
    
    # Получаем информацию о занятии перед удалением
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM schedule WHERE id = ?", (schedule_id,)
        ) as cursor:
            schedule_item = await cursor.fetchone()
            
    if not schedule_item:
        await callback_query.answer("Ошибка: занятие не найдено.")
        return
    
    # Удаляем занятие из расписания
    success = await db.delete_schedule_item(schedule_id)
    
    if not success:
        await callback_query.answer("Ошибка при удалении занятия.")
        return
    
    # Отправляем уведомление студентам группы
    group_code = schedule_item["group_code"]
    weekday = schedule_item["weekday"]
    time = schedule_item["time"]
    subject = schedule_item["subject"]
    
    students_notified = await send_schedule_notification(
        callback_query.bot, group_code, "delete", weekday, time, subject
    )
    
    # Обновляем сообщение, удаляя кнопку
    await callback_query.message.edit_reply_markup(reply_markup=None)
    
    # Отвечаем на callback
    await callback_query.answer(f"Занятие удалено. Уведомлены {students_notified} студентов.")
    
    # Отправляем сообщение о успешном удалении
    await callback_query.message.answer(
        f"Занятие {weekday}, {time} - {subject} удалено из расписания группы {group_code}.\n"
        f"Уведомления отправлены {students_notified} студентам."
    )

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    dp.register_message_handler(cmd_schedule, commands=["schedule"], state="*")
    dp.register_message_handler(process_schedule_action, state=ScheduleStates.waiting_for_action)
    dp.register_message_handler(process_select_group, state=ScheduleStates.selecting_group)  # Добавляем обработчик выбора группы
    dp.register_message_handler(process_add_schedule_weekday, state=ScheduleStates.add_schedule_weekday)
    dp.register_message_handler(process_add_schedule_time, state=ScheduleStates.add_schedule_time)
    dp.register_message_handler(process_add_schedule_subject, state=ScheduleStates.add_schedule_subject)
    dp.register_callback_query_handler(process_edit_schedule_callback, lambda c: c.data.startswith("edit_schedule_"), state=ScheduleStates.edit_schedule_item)
    dp.register_message_handler(process_edit_schedule_weekday, state=ScheduleStates.edit_schedule_weekday)
    dp.register_message_handler(process_edit_schedule_time, state=ScheduleStates.edit_schedule_time)
    dp.register_message_handler(process_edit_schedule_subject, state=ScheduleStates.edit_schedule_subject)
    dp.register_callback_query_handler(process_delete_schedule_callback, lambda c: c.data.startswith("delete_schedule_"))
    dp.register_message_handler(process_confirm_schedule_change, state=ScheduleStates.confirm_schedule_change)
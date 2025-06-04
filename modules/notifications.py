# notifications.py
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from localization.kz_text import NOTIFICATION_MESSAGES, NOTIFICATION_TYPES, SCHEDULE_NOTIFICATIONS, GROUP_MESSAGES

# Обработчик команды /notifications
async def cmd_notifications(message: types.Message):
    user = await db.get_user(message.from_user.id)
    
    if not user or user["status"] != "approved":
        await message.answer(NOTIFICATION_MESSAGES["not_registered"])
        return
    
    # Получаем непрочитанные уведомления пользователя
    notifications = await db.get_unread_notifications(message.from_user.id)
    
    if not notifications:
        await message.answer(NOTIFICATION_MESSAGES["no_notifications"])
        return
    
    # Создаем инлайн-клавиатуру с кнопками для отметки уведомлений как прочитанных
    for notification in notifications:
        # Определяем тип уведомления для вывода соответствующей иконки
        notification_type = notification["notification_type"] if "notification_type" in notification.keys() else "general"
        type_prefix = NOTIFICATION_TYPES.get(notification_type, NOTIFICATION_TYPES["general"])
        
        # Для каждого уведомления создаем отдельное сообщение с кнопкой
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            NOTIFICATION_MESSAGES["mark_as_read"],
            callback_data=f"read_notification_{notification['id']}"
        ))
        
        # Отправляем уведомление с кнопкой
        await message.answer(
            f"{type_prefix} {notification['message']}\n\n"
            f"{NOTIFICATION_MESSAGES['notification_from'].format(date=notification['created_at'])}",
            reply_markup=keyboard
        )

# Обработчик нажатия на кнопку "Отметить как прочитанное"
async def process_read_notification(callback_query: types.CallbackQuery):
    # Извлекаем ID уведомления из callback_data
    notification_id = int(callback_query.data.split("_")[2])
    
    # Отмечаем уведомление как прочитанное
    await db.mark_notification_as_read(notification_id)
    
    # Обновляем сообщение, убирая кнопку
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        # В случае ошибки редактирования (например, прошло более 48 часов)
        pass
    
    # Отвечаем на callback
    await callback_query.answer(NOTIFICATION_MESSAGES["marked_as_read"])

# Отправка уведомления всем студентам группы
async def send_group_notification(bot, group_code, message_text, notification_type="general"):
    # Получаем всех студентов группы
    students = await db.get_students_by_group(group_code)
    
    # Отправляем уведомление каждому студенту
    for student in students:
        try:
            # Добавляем уведомление в базу
            await db.add_notification(student["telegram_id"], message_text, notification_type)
            
            # Определяем префикс уведомления
            type_prefix = NOTIFICATION_TYPES.get(notification_type, NOTIFICATION_TYPES["general"])
            
            # Отправляем сообщение
            await bot.send_message(student["telegram_id"], f"{type_prefix} {message_text}")
        except Exception:
            # Если не удалось отправить сообщение студенту
            pass
    
    return len(students)

# Отправка уведомления об изменении расписания студентам группы
async def send_schedule_notification(bot, group_code, change_type, weekday, time, subject):
    message = None
    
    # Формируем сообщение в зависимости от типа изменения
    if change_type == "add":
        message = SCHEDULE_NOTIFICATIONS["lesson_added"].format(
            group_code=group_code,
            weekday=weekday,
            time=time,
            subject=subject
        )
    elif change_type == "update":
        message = SCHEDULE_NOTIFICATIONS["lesson_updated"].format(
            group_code=group_code,
            weekday=weekday,
            time=time,
            subject=subject
        )
    elif change_type == "delete":
        message = SCHEDULE_NOTIFICATIONS["lesson_deleted"].format(
            group_code=group_code,
            weekday=weekday,
            time=time,
            subject=subject
        )
    
    if message:
        # Отправляем уведомления всем студентам группы
        return await send_group_notification(bot, group_code, message, "schedule")
    
    return 0

# Отправка персонального уведомления студенту
async def send_personal_notification(bot, student_id, message_text, notification_type="general"):
    # Добавляем уведомление в базу данных в любом случае
    try:
        await db.add_notification(student_id, message_text, notification_type)
    except Exception as e:
        print(f"[ҚАТЕ] Хабарламаны дерекқорға қосу сәтсіз болды: {e}")
        return False
    
    # Определяем префикс уведомления
    type_prefix = NOTIFICATION_TYPES.get(notification_type, NOTIFICATION_TYPES["general"])
    
    # Пытаемся отправить сообщение
    try:
        await bot.send_message(student_id, f"{type_prefix} {message_text}")
        return True
    except Exception as e:
        error_message = str(e)
        if "bot was blocked by the user" in error_message:
            print(f"[ҚАТЕ] Студент (ID: {student_id}) ботты бұғаттады")
        elif "chat not found" in error_message:
            print(f"[ҚАТЕ] Студентпен чат (ID: {student_id}) табылмады. Студент ботпен сөйлесуді бастамаған шығар")
        else:
            print(f"[ҚАТЕ] Студентке хабарлама жіберу сәтсіз болды (ID: {student_id}): {e}")
        return False

# Отправка уведомления о переводе в другую группу
async def send_group_change_notification(bot, student_id, old_group, new_group):
    message = GROUP_MESSAGES["group_transfer_notification"].format(
        old_group=old_group,
        new_group=new_group
    )
    return await send_personal_notification(bot, student_id, message, "group")

# Регистрация обработчиков в диспетчере
def register_handlers(dp):
    dp.register_message_handler(cmd_notifications, commands=["notifications"])
    dp.register_callback_query_handler(
        process_read_notification,
        lambda c: c.data.startswith("read_notification_")
    )

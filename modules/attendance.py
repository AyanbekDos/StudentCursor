# attendance.py
import json
import logging
import io
import qrcode
from datetime import datetime, timedelta
from PIL import Image
from pyzbar.pyzbar import decode
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import QR_CODE_VALIDITY_MINUTES
from database.db import db
from localization.kz_text import ATTENDANCE_MESSAGES, BUTTONS
from modules.keyboards import get_student_keyboard

logger = logging.getLogger(__name__)

# Определение состояний для FSM (Finite State Machine)
class QRGenerationStates(StatesGroup):
    waiting_for_group = State()
    waiting_for_subject = State()

# Функция для генерации QR-кода
async def generate_qr_code(group_id, subject):
    """
    Генерирует QR-код с данными о посещаемости
    Args:
        group_id (int): ID группы
        subject (str): Название предмета
    Returns:
        BytesIO: Изображение QR-кода в байтовом формате
    """
    # Текущее время в ISO формате
    timestamp = datetime.now().isoformat()
    
    # Данные для QR-кода
    qr_data = {
        "type": "attendance",
        "group_id": group_id,
        "subject": subject,
        "timestamp": timestamp
    }
    
    # Преобразуем данные в JSON строку
    qr_json = json.dumps(qr_data)
    
    # Генерируем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_json)
    qr.make(fit=True)
    
    # Создаем изображение QR-кода
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Сохраняем изображение в байтовый буфер
    img_byte_array = io.BytesIO()
    img.save(img_byte_array, format='PNG')
    img_byte_array.seek(0)
    
    return img_byte_array

# Обработчик команды /qr для преподавателя
async def cmd_qr(message: types.Message, state: FSMContext):
    """
    Обработчик команды /qr для преподавателя.
    Начинает процесс генерации QR-кода для отметки посещаемости.
    """
    user = await db.get_user(message.from_user.id)
    
    # Проверяем, что пользователь - преподаватель
    if not user or user['role'] != 'teacher':
        await message.answer(ATTENDANCE_MESSAGES["teacher_only_qr"])
        return
    
    # Получаем список групп для преподавателя
    groups = await db.get_groups_for_teacher(message.from_user.id)
    
    if not groups:
        await message.answer(ATTENDANCE_MESSAGES["no_groups_teacher"])
        return
    
    # Создаем клавиатуру для выбора группы
    keyboard = InlineKeyboardMarkup(row_width=1)
    for group_id, group_name in groups:
        keyboard.add(InlineKeyboardButton(text=group_name, callback_data=f"qr_group_{group_id}"))
    
    await message.answer(ATTENDANCE_MESSAGES["choose_group_qr"], reply_markup=keyboard)
    await QRGenerationStates.waiting_for_group.set()

# Обработчик выбора группы
async def process_group_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор группы преподавателем и предлагает выбрать предмет
    """
    # Извлекаем ID группы из callback_data
    group_id = int(callback_query.data.split('_')[-1])
    
    # Сохраняем ID группы в состоянии
    await state.update_data(group_id=group_id)
    
    # Получаем список предметов для выбранной группы
    subjects = await db.get_subjects_for_group(group_id)
    
    if not subjects:
        await callback_query.message.answer(ATTENDANCE_MESSAGES["no_subjects_group"])
        await state.finish()
        return
    
    # Создаем клавиатуру для выбора предмета
    keyboard = InlineKeyboardMarkup(row_width=1)
    for subject in subjects:
        keyboard.add(InlineKeyboardButton(text=subject, callback_data=f"qr_subject_{subject}"))
    
    await callback_query.message.answer(ATTENDANCE_MESSAGES["choose_subject_qr"], reply_markup=keyboard)
    await QRGenerationStates.waiting_for_subject.set()
    
    # Отвечаем на callback_query, чтобы убрать часы загрузки
    await callback_query.answer()

# Обработчик выбора предмета
async def process_subject_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор предмета преподавателем и генерирует QR-код
    """
    # Извлекаем название предмета из callback_data
    subject = callback_query.data.split('_', 2)[-1]
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    group_id = state_data.get('group_id')
    
    # Генерируем QR-код
    qr_image = await generate_qr_code(group_id, subject)
    
    # Отправляем QR-код преподавателю
    await callback_query.message.answer_photo(
        qr_image,
        caption=ATTENDANCE_MESSAGES["qr_generated"].format(minutes=QR_CODE_VALIDITY_MINUTES)
    )
    
    # Завершаем состояние
    await state.finish()
    
    # Отвечаем на callback_query, чтобы убрать часы загрузки
    await callback_query.answer()

# Обработчик фотографий от студентов
async def process_photo(message: types.Message):
    """
    Обрабатывает фотографии от студентов для отметки посещаемости
    """
    # Проверяем, что пользователь - студент
    user = await db.get_user(message.from_user.id)
    
    if not user or user['role'] != 'student' or user['status'] != 'approved':
        await message.answer(ATTENDANCE_MESSAGES["approved_students_only"])
        return
    
    student_telegram_id = message.from_user.id
    
    try:
        # Получаем фото с наибольшим размером
        photo = message.photo[-1]
        
        # Скачиваем фото
        photo_file = await message.bot.download_file_by_id(photo.file_id)
        
        # Открываем изображение с помощью PIL
        image = Image.open(photo_file)
        
        # Декодируем QR-код
        decoded_objects = decode(image)
        
        if not decoded_objects:
            # QR-код не найден
            await db.add_attendance_record(
                student_id=student_telegram_id,
                subject="unknown",
                qr_timestamp=datetime.now().isoformat(),
                submission_timestamp=datetime.now().isoformat(),
                status="ERROR_INVALID_QR",
                group_id=None
            )
            await message.answer(ATTENDANCE_MESSAGES["qr_not_recognized"])
            return
        
        # Берем первый найденный QR-код
        qr_data_str = decoded_objects[0].data.decode('utf-8')
        
        try:
            # Парсим JSON данные из QR-кода
            qr_data = json.loads(qr_data_str)
            
            # Проверяем тип QR-кода
            if qr_data.get("type") != "attendance":
                await db.add_attendance_record(
                    student_id=student_telegram_id,
                    subject="unknown",
                    qr_timestamp=datetime.now().isoformat(),
                    submission_timestamp=datetime.now().isoformat(),
                    status="ERROR_INVALID_QR",
                    group_id=None
                )
                await message.answer(ATTENDANCE_MESSAGES["invalid_qr_type"])
                return
            
            # Извлекаем данные из QR-кода
            group_id_from_qr = qr_data.get("group_id")
            subject_from_qr = qr_data.get("subject")
            timestamp_from_qr = qr_data.get("timestamp")
            
            # Проверка срока действия QR-кода
            qr_datetime = datetime.fromisoformat(timestamp_from_qr)
            current_datetime = datetime.now()
            
            if current_datetime - qr_datetime > timedelta(minutes=QR_CODE_VALIDITY_MINUTES):
                await db.add_attendance_record(
                    student_id=student_telegram_id,
                    subject=subject_from_qr,
                    qr_timestamp=timestamp_from_qr,
                    submission_timestamp=current_datetime.isoformat(),
                    status="ERROR_EXPIRED",
                    group_id=group_id_from_qr
                )
                await message.answer(ATTENDANCE_MESSAGES["qr_expired"])
                return
            
            # Проверка группы студента
            student_group_id = await db.get_student_group_id(student_telegram_id)
            
            if student_group_id != group_id_from_qr:
                await db.add_attendance_record(
                    student_id=student_telegram_id,
                    subject=subject_from_qr,
                    qr_timestamp=timestamp_from_qr,
                    submission_timestamp=current_datetime.isoformat(),
                    status="ERROR_GROUP_MISMATCH",
                    group_id=group_id_from_qr
                )
                await message.answer(ATTENDANCE_MESSAGES["wrong_group"])
                return
            
            # Проверка на дубликат
            if await db.check_if_already_attended(student_telegram_id, subject_from_qr, timestamp_from_qr):
                await db.add_attendance_record(
                    student_id=student_telegram_id,
                    subject=subject_from_qr,
                    qr_timestamp=timestamp_from_qr,
                    submission_timestamp=current_datetime.isoformat(),
                    status="ERROR_DUPLICATE",
                    group_id=group_id_from_qr
                )
                await message.answer(ATTENDANCE_MESSAGES["already_checked"])
                return
            
            # Все проверки пройдены, записываем успешную отметку
            await db.add_attendance_record(
                student_id=student_telegram_id,
                subject=subject_from_qr,
                qr_timestamp=timestamp_from_qr,
                submission_timestamp=current_datetime.isoformat(),
                status="PRESENT",
                group_id=group_id_from_qr
            )
            
            # Отправляем сообщение об успешной отметке
            await message.answer(ATTENDANCE_MESSAGES["attendance_saved"])
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Ошибка при парсинге данных QR-кода
            logger.error(f"Ошибка при обработке QR-кода: {e}")
            await db.add_attendance_record(
                student_id=student_telegram_id,
                subject="unknown",
                qr_timestamp=datetime.now().isoformat(),
                submission_timestamp=datetime.now().isoformat(),
                status="ERROR_INVALID_QR",
                group_id=None
            )
            await message.answer(ATTENDANCE_MESSAGES["attendance_error"])
            
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await message.answer(ATTENDANCE_MESSAGES["photo_error"])

# Обработчик команды /checkin и кнопки "Белгілеу"
async def cmd_checkin(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /checkin и нажатие на кнопку "Белгілеу"
    Показывает инструкцию по отметке посещаемости
    """
    user = await db.get_user(message.from_user.id)
    
    # Проверяем, что пользователь - студент
    if not user or user['role'] != 'student':
        await message.answer(ATTENDANCE_MESSAGES["student_only_checkin"])
        return
    
    # Получаем клавиатуру студента
    keyboard = get_student_keyboard()
    
    # Инструкция по отметке посещаемости
    instructions = ATTENDANCE_MESSAGES["checkin_instructions"].format(minutes=QR_CODE_VALIDITY_MINUTES)
    
    await message.answer(instructions, reply_markup=keyboard)

# Регистрация обработчиков
def register_handlers(dp):
    """
    Регистрирует обработчики для модуля посещаемости
    Args:
        dp: Диспетчер бота
    """
    # Команда /qr для преподавателя
    dp.register_message_handler(cmd_qr, commands=["qr"])
    
    # Команда /checkin для студента
    dp.register_message_handler(cmd_checkin, commands=["checkin"])
    
    # Обработчики для FSM
    dp.register_callback_query_handler(
        process_group_selection,
        lambda c: c.data.startswith('qr_group_'),
        state=QRGenerationStates.waiting_for_group
    )
    
    dp.register_callback_query_handler(
        process_subject_selection,
        lambda c: c.data.startswith('qr_subject_'),
        state=QRGenerationStates.waiting_for_subject
    )
    
    # Обработчик фотографий от студентов
    dp.register_message_handler(
        process_photo,
        content_types=types.ContentType.PHOTO
    )

import random
import asyncio
import os
import json
import io
import qrcode
from datetime import datetime, timedelta
import logging

from database.db import db
from config import SUBJECTS, WEEKDAYS, QR_CODE_VALIDITY_MINUTES

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция для генерации случайного имени
def generate_random_name():
    first_names = [
        "Александр", "Дмитрий", "Максим", "Иван", "Артём", "Михаил", "Даниил", "Никита",
        "Анна", "Мария", "Елена", "Дарья", "Алиса", "Виктория", "Екатерина", "Наталья"
    ]
    last_names = [
        "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов",
        "Михайлов", "Новиков", "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев"
    ]
    patronymics = [
        "Александрович", "Дмитриевич", "Максимович", "Иванович", "Артёмович", "Михайлович",
        "Александровна", "Дмитриевна", "Максимовна", "Ивановна", "Артёмовна", "Михайловна"
    ]
    
    full_name = f"{random.choice(last_names)} {random.choice(first_names)} {random.choice(patronymics)}"
    return full_name

# Функция для генерации случайной даты в прошлом
def generate_random_date():
    today = datetime.now()
    days_ago = random.randint(1, 60)  # Случайная дата за последние 60 дней
    random_date = today - timedelta(days=days_ago)
    return random_date.strftime("%d.%m.%Y")

# Функция для генерации тестовых данных
async def generate_fake_data():
    try:
        # Инициализируем базу данных
        await db.init()
        logger.info("База данных инициализирована")
        
        # Создаем 2 группы
        groups = ["ИС-21", "БТ-22"]
        for group in groups:
            await db.add_group(group)
        logger.info(f"Созданы группы: {', '.join(groups)}")
        
        # Создаем 2 преподавателей
        teachers = []
        for i in range(1, 3):
            teacher_id = 1000 + i
            full_name = generate_random_name()
            await db.add_user(teacher_id, full_name, "teacher", status="approved")
            teachers.append({"id": teacher_id, "name": full_name})
        logger.info(f"Созданы преподаватели: {len(teachers)}")
        
        # Назначаем преподавателей группам
        for i, group in enumerate(groups):
            teacher = teachers[i]
            await db.add_group(group, teacher["id"])
        logger.info("Преподаватели назначены группам")
        
        # Создаем 10 студентов в каждой группе
        students = []
        student_id_start = 2000
        
        for group in groups:
            for i in range(10):
                student_id = student_id_start + i
                full_name = generate_random_name()
                await db.add_user(student_id, full_name, "student", group, "approved")
                students.append({"id": student_id, "name": full_name, "group": group})
            student_id_start += 10
        logger.info(f"Созданы студенты: {len(students)}")
        
        # Создаем расписание для каждой группы
        time_slots = ["09:00", "10:45", "12:30", "14:15", "16:00"]
        schedule_items = 0
        
        for group in groups:
            for weekday in WEEKDAYS[:5]:  # Только будние дни
                # Выбираем 2-3 случайных временных слота для каждого дня
                selected_slots = random.sample(time_slots, random.randint(2, 3))
                for time_slot in selected_slots:
                    subject = random.choice(SUBJECTS)
                    await db.add_schedule_item(group, weekday, time_slot, subject)
                    schedule_items += 1
        logger.info(f"Создано элементов расписания: {schedule_items}")
        
        # Выставляем оценки студентам
        grades_count = 0
        for student in students:
            # 3-5 оценок для каждого студента
            num_grades = random.randint(3, 5)
            for _ in range(num_grades):
                subject = random.choice(SUBJECTS)
                date = generate_random_date()
                grade = random.randint(3, 5)  # Оценки от 3 до 5
                
                # 50% шанс на комментарий
                comment = None
                if random.random() > 0.5:
                    comments = [
                        "Отличная работа!", "Хорошо справился с заданием", 
                        "Есть некоторые недочеты", "Нужно доработать", 
                        "Молодец!", "Старайся лучше"
                    ]
                    comment = random.choice(comments)
                
                await db.add_grade(student["id"], subject, date, grade, comment)
                grades_count += 1
        logger.info(f"Создано оценок: {grades_count}")
        
        # Добавляем несколько уведомлений
        notifications_count = 0
        for student in students:
            notification_types = [
                "Изменение в расписании: завтра отмена занятия по Информатике.",
                "Напоминание: завтра контрольная работа по Физике.",
                "Объявление: в следующий вторник состоится встреча с куратором.",
                "Изменение в расписании: занятие по Истории перенесено на 15:30."
            ]
            
            # 0-2 уведомления для каждого студента
            num_notifications = random.randint(0, 2)
            for _ in range(num_notifications):
                message = random.choice(notification_types)
                await db.add_notification(student["id"], message)
                notifications_count += 1
        logger.info(f"Создано уведомлений: {notifications_count}")
        
        # Генерация тестовых записей посещаемости
        attendance_count = 0
        for student in students:
            # Для каждого студента создаем 1-2 тестовые записи посещения
            num_attendance = random.randint(1, 2)
            for _ in range(num_attendance):
                subject = random.choice(SUBJECTS)
                qr_timestamp = (datetime.now() - timedelta(days=random.randint(1, 10))).isoformat()
                submission_timestamp = (datetime.fromisoformat(qr_timestamp) + timedelta(minutes=random.randint(0, QR_CODE_VALIDITY_MINUTES-1))).isoformat()
                status = random.choice(["PRESENT", "ERROR_EXPIRED", "ERROR_DUPLICATE", "ERROR_GROUP_MISMATCH"])
                # Получаем group_id через db.get_student_group_id
                group_id = await db.get_student_group_id(student["id"])
                await db.add_attendance_record(student["id"], subject, qr_timestamp, submission_timestamp, status, group_id)
                attendance_count += 1
        logger.info(f"Создано тестовых записей посещаемости: {attendance_count}")

        # Генерация примера QR-кода для ручного теста
        await generate_sample_qr_png()
        logger.info("Сгенерирован пример QR-кода: sample_qr.png")

        return {
            "groups": groups,
            "teachers": teachers,
            "students": students,
            "grades": grades_count,
            "notifications": notifications_count,
            "attendance": attendance_count
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации тестовых данных: {e}")
        raise

# Функция для запуска генерации тестовых данных
async def run_fake_data_generation():
    try:
        logger.info("Начало генерации тестовых данных...")
        result = await generate_fake_data()
        
        logger.info("Тестовые данные успешно сгенерированы!")
        logger.info(f"Создано групп: {len(result['groups'])}")
        logger.info(f"Создано преподавателей: {len(result['teachers'])}")
        logger.info(f"Создано студентов: {len(result['students'])}")
        logger.info(f"Создано оценок: {result['grades']}")
        logger.info(f"Создано уведомлений: {result['notifications']}")
        
        logger.info("Генерация тестовых данных завершена успешно!")
    except Exception as e:
        logger.error(f"Ошибка при генерации тестовых данных: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Функция для генерации и сохранения примера QR-кода
async def generate_sample_qr_png():
    """
    Генерирует и сохраняет пример QR-кода для ручного теста (sample_qr.png)
    """
    # Пример данных: группа с id=1, предмет "Математика", текущее время
    qr_data = {
        "type": "attendance",
        "group_id": 1,
        "subject": "Математика",
        "timestamp": datetime.now().isoformat()
    }
    qr_json = json.dumps(qr_data)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_json)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("sample_qr.png")

if __name__ == "__main__":
    # Запускаем генерацию данных при прямом вызове скрипта
    asyncio.run(run_fake_data_generation()) 
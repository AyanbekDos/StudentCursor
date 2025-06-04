import os
import aiosqlite
import asyncio
from pathlib import Path
from config import DATABASE_PATH

class Database:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        # Создаем родительские каталоги, если они не существуют
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
    async def init(self):
        """Инициализация базы данных и создание таблиц"""
        # Чтение SQL-схемы
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            schema = schema_file.read()
            
        # Подключение к БД и создание таблиц
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()
            
    # Методы для работы с пользователями
    async def add_user(self, telegram_id, full_name, role, group_code=None, status="pending"):
        """Добавление нового пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (telegram_id, full_name, role, group_code, status) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, full_name, role, group_code, status)
            )
            await db.commit()
            
    async def get_user(self, telegram_id):
        """Получение информации о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                return await cursor.fetchone()
                
    async def update_user_status(self, telegram_id, status):
        """Обновление статуса пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (status, telegram_id)
            )
            await db.commit()
            
    async def delete_user(self, telegram_id):
        """Удаление пользователя из базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()
            
    async def update_user_group(self, telegram_id, new_group_code):
        """Обновляет группу пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET group_code = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (new_group_code, telegram_id)
            )
            await db.commit()
            
    async def get_pending_students(self):
        """Получение списка студентов, ожидающих подтверждения"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE role = 'student' AND status = 'pending'"
            ) as cursor:
                return await cursor.fetchall()
                
    # Методы для работы с группами
    async def add_group(self, group_code, teacher_telegram_id=None):
        """Добавление новой группы"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO groups (group_code, teacher_telegram_id) VALUES (?, ?)",
                (group_code, teacher_telegram_id)
            )
            await db.commit()
            
    async def get_groups(self):
        """Получение списка всех групп"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM groups") as cursor:
                return await cursor.fetchall()
                
    async def get_students_by_group(self, group_code):
        """Получение списка студентов определенной группы"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE group_code = ? AND role = 'student' AND status = 'approved'",
                (group_code,)
            ) as cursor:
                return await cursor.fetchall()
                
    # Методы для работы с расписанием
    async def add_schedule_item(self, group_code, weekday, time, subject):
        """Добавление элемента расписания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO schedule (group_code, weekday, time, subject) VALUES (?, ?, ?, ?)",
                (group_code, weekday, time, subject)
            )
            schedule_id = cursor.lastrowid
            await db.commit()
            
            # Добавляем запись в историю изменений
            await db.execute(
                "INSERT INTO schedule_changes (schedule_id, group_code, change_type, weekday, time, subject) VALUES (?, ?, ?, ?, ?, ?)",
                (schedule_id, group_code, "add", weekday, time, subject)
            )
            await db.commit()
            
            return schedule_id
            
    async def update_schedule_item(self, id, weekday, time, subject):
        """Обновление элемента расписания"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем информацию о текущем элементе расписания для log
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM schedule WHERE id = ?", (id,)) as cursor:
                schedule_item = await cursor.fetchone()
                
            if not schedule_item:
                return False
                
            # Обновляем элемент расписания
            await db.execute(
                "UPDATE schedule SET weekday = ?, time = ?, subject = ? WHERE id = ?",
                (weekday, time, subject, id)
            )
            
            # Добавляем запись в историю изменений
            await db.execute(
                "INSERT INTO schedule_changes (schedule_id, group_code, change_type, weekday, time, subject) VALUES (?, ?, ?, ?, ?, ?)",
                (id, schedule_item["group_code"], "update", weekday, time, subject)
            )
            
            await db.commit()
            return True
            
    async def delete_schedule_item(self, id):
        """Удаление элемента расписания"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем информацию о текущем элементе расписания для log
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM schedule WHERE id = ?", (id,)) as cursor:
                schedule_item = await cursor.fetchone()
                
            if not schedule_item:
                return False
                
            # Добавляем запись в историю изменений
            await db.execute(
                "INSERT INTO schedule_changes (schedule_id, group_code, change_type, weekday, time, subject) VALUES (?, ?, ?, ?, ?, ?)",
                (id, schedule_item["group_code"], "delete", schedule_item["weekday"], schedule_item["time"], schedule_item["subject"])
            )
            
            # Удаляем элемент расписания
            await db.execute("DELETE FROM schedule WHERE id = ?", (id,))
            await db.commit()
            return True
            
    async def get_schedule(self, group_code):
        """Получение расписания для группы"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM schedule WHERE group_code = ? ORDER BY CASE weekday "
                "WHEN 'Пн' THEN 1 WHEN 'Вт' THEN 2 WHEN 'Ср' THEN 3 "
                "WHEN 'Чт' THEN 4 WHEN 'Пт' THEN 5 WHEN 'Сб' THEN 6 "
                "WHEN 'Вс' THEN 7 END, time",
                (group_code,)
            ) as cursor:
                return await cursor.fetchall()
                
    async def get_last_schedule_change(self, group_code):
        """Получение последнего изменения расписания для группы"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM schedule_changes WHERE group_code = ? ORDER BY created_at DESC LIMIT 1",
                (group_code,)
            ) as cursor:
                return await cursor.fetchone()
                
    # Методы для работы с оценками
    async def add_grade(self, student_id, subject, date, grade, comment=None):
        """Добавление оценки"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO grades (student_id, subject, date, grade, comment) VALUES (?, ?, ?, ?, ?)",
                (student_id, subject, date, grade, comment)
            )
            await db.commit()
            
    async def get_student_grades(self, student_id):
        """Получение всех оценок студента"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM grades WHERE student_id = ? ORDER BY date DESC",
                (student_id,)
            ) as cursor:
                return await cursor.fetchall()
                
    async def get_teacher_grades(self, teacher_id):
        """Получение всех оценок, выставленных преподавателем"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Получаем группы преподавателя
            async with db.execute(
                "SELECT group_code FROM groups WHERE teacher_telegram_id = ?",
                (teacher_id,)
            ) as cursor:
                groups = await cursor.fetchall()
                
            if not groups:
                return []
                
            # Получаем студентов из этих групп
            group_codes = [group["group_code"] for group in groups]
            placeholders = ", ".join(["?" for _ in group_codes])
            
            # Получаем все оценки студентов из групп преподавателя
            query = f"""
            SELECT g.*, u.full_name, u.group_code 
            FROM grades g
            JOIN users u ON g.student_id = u.telegram_id
            WHERE u.group_code IN ({placeholders})
            ORDER BY g.date DESC, u.group_code, u.full_name
            """
            
            async with db.execute(query, group_codes) as cursor:
                return await cursor.fetchall()
                
    async def get_student_grades_by_subject(self, student_id, subject):
        """Получение оценок студента по конкретному предмету"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM grades WHERE student_id = ? AND subject = ? ORDER BY date DESC",
                (student_id, subject)
            ) as cursor:
                return await cursor.fetchall()
                
    # Методы для работы с уведомлениями
    async def add_notification(self, user_id, message, notification_type="general"):
        """Добавление уведомления"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO notifications (user_id, message, notification_type) VALUES (?, ?, ?)",
                (user_id, message, notification_type)
            )
            await db.commit()
            
    async def mark_notification_as_read(self, notification_id):
        """Отметка уведомления как прочитанного"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE notifications SET is_read = TRUE WHERE id = ?",
                (notification_id,)
            )
            await db.commit()
            
    async def get_unread_notifications(self, user_id):
        """Получение непрочитанных уведомлений пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM notifications WHERE user_id = ? AND is_read = FALSE ORDER BY created_at DESC",
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()
                
    async def get_unread_notifications_by_type(self, user_id, notification_type):
        """Получение непрочитанных уведомлений пользователя по типу"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM notifications WHERE user_id = ? AND notification_type = ? AND is_read = FALSE ORDER BY created_at DESC",
                (user_id, notification_type)
            ) as cursor:
                return await cursor.fetchall()
    
    # Методы для работы с посещаемостью
    async def add_attendance_record(self, student_id, subject, qr_timestamp, submission_timestamp, status, group_id):
        """Добавляет запись о посещаемости"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO attendance (student_id, subject, qr_timestamp, submission_timestamp, status, group_id) VALUES (?, ?, ?, ?, ?, ?)",
                (student_id, subject, qr_timestamp, submission_timestamp, status, group_id)
            )
            await db.commit()
    
    async def check_if_already_attended(self, student_id, subject, qr_timestamp):
        """Проверяет, есть ли уже отметка PRESENT для данного студента, предмета и сессии"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM attendance WHERE student_id = ? AND subject = ? AND qr_timestamp = ? AND status = 'PRESENT'",
                (student_id, subject, qr_timestamp)
            ) as cursor:
                result = await cursor.fetchone()
                return result is not None
    
    async def get_student_group_id(self, student_telegram_id):
        """Возвращает ID группы студента по его Telegram ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT group_code FROM users WHERE telegram_id = ? AND role = 'student'",
                (student_telegram_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result and result['group_code']:
                    # Получаем ID группы по её коду
                    async with db.execute(
                        "SELECT rowid as id FROM groups WHERE group_code = ?",
                        (result['group_code'],)
                    ) as group_cursor:
                        group = await group_cursor.fetchone()
                        return group['id'] if group else None
                return None
    
    async def get_groups_for_teacher(self, teacher_telegram_id=None):
        """Возвращает список кортежей (group_id, group_name) для выбора преподавателем"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if teacher_telegram_id:
                # Для преподавателя возвращаем все группы, где он указан как преподаватель
                query = """
                SELECT rowid as id, group_code 
                FROM groups
                WHERE teacher_telegram_id = ?
                """
                params = [teacher_telegram_id]
            else:
                # Для администратора возвращаем все группы
                query = "SELECT rowid as id, group_code FROM groups"
                params = []
                
            async with db.execute(query, params) as cursor:
                groups = await cursor.fetchall()
                return [(group['id'], group['group_code']) for group in groups]
    
    async def get_subjects_for_group(self, group_id):
        """Возвращает список предметов для указанной группы"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Сначала получаем код группы по ID
            async with db.execute(
                "SELECT group_code FROM groups WHERE rowid = ?",
                (group_id,)
            ) as cursor:
                group = await cursor.fetchone()
                if not group:
                    return []
                
                group_code = group['group_code']
                
                # Теперь получаем уникальные предметы из расписания для этой группы
                async with db.execute(
                    "SELECT DISTINCT subject FROM schedule WHERE group_code = ?",
                    (group_code,)
                ) as cursor:
                    subjects = await cursor.fetchall()
                    return [subject['subject'] for subject in subjects]
                
    async def delete_user(self, telegram_id):
        """Удаление пользователя из базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем пользователя
            await db.execute(
                "DELETE FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            # Удаляем все уведомления пользователя
            await db.execute(
                "DELETE FROM notifications WHERE user_id = ?",
                (telegram_id,)
            )
            # Удаляем все записи о посещаемости пользователя (если это студент)
            await db.execute(
                "DELETE FROM attendance WHERE student_id = ?",
                (telegram_id,)
            )
            # Удаляем все оценки пользователя (если это студент)
            await db.execute(
                "DELETE FROM grades WHERE student_id = ?",
                (telegram_id,)
            )
            await db.commit()
            return True

    async def delete_group(self, group_code):
        """Удаляет группу и все связанные с ней данные"""
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем расписание группы
            await db.execute(
                "DELETE FROM schedule WHERE group_code = ?",
                (group_code,)
            )
            
            # Удаляем изменения расписания группы
            await db.execute(
                "DELETE FROM schedule_changes WHERE group_code = ?",
                (group_code,)
            )
            
            # Удаляем саму группу
            await db.execute(
                "DELETE FROM groups WHERE group_code = ?",
                (group_code,)
            )
            
            await db.commit()
            return True

# Создание экземпляра базы данных
db = Database()
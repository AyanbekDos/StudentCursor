import asyncio
import aiosqlite
import sys
from config import DATABASE_PATH

# Устанавливаем кодировку для вывода в консоль
sys.stdout.reconfigure(encoding='utf-8')

async def reset_users():
    """Удаляет пользователей из базы данных для повторной регистрации"""
    
    print("Начинаю процесс удаления пользователей...")
    
    try:
        # Подключаемся к базе данных
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Получаем список всех пользователей для отображения
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT telegram_id, full_name, role, group_code FROM users") as cursor:
                users = await cursor.fetchall()
                
            if not users:
                print("В базе данных нет пользователей.")
                return
                
            print("\nСписок пользователей в базе данных:")
            print("-" * 50)
            for i, user in enumerate(users, 1):
                print(f"{i}. ID: {user['telegram_id']}, Имя: {user['full_name']}, Роль: {user['role']}, Группа: {user['group_code']}")
            print("-" * 50)
            
            # Запрашиваем ID пользователей для удаления
            ids_to_delete = input("\nВведите ID пользователей для удаления через запятую: ")
            ids_list = [int(id.strip()) for id in ids_to_delete.split(",") if id.strip().isdigit()]
            
            if not ids_list:
                print("Не указаны корректные ID для удаления.")
                return
                
            # Удаляем пользователей
            for user_id in ids_list:
                # Удаляем связанные записи
                # Удаляем оценки
                await db.execute("DELETE FROM grades WHERE student_id = ?", (user_id,))
                # Удаляем уведомления
                await db.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                # Удаляем записи о посещаемости
                await db.execute("DELETE FROM attendance WHERE student_id = ?", (user_id,))
                # Удаляем пользователя
                await db.execute("DELETE FROM users WHERE telegram_id = ?", (user_id,))
                
            # Сохраняем изменения
            await db.commit()
            
            print(f"\nУспешно удалены пользователи с ID: {', '.join(map(str, ids_list))}")
            print("Теперь вы можете заново зарегистрировать этих пользователей в боте.")
            
    except Exception as e:
        print(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(reset_users())

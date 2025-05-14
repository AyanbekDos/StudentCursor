import asyncio
import aiosqlite
from config import DATABASE_PATH

async def delete_test_users():
    # ID пользователей, которых нужно удалить
    user_ids = [34975055, 7059952799]
    
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Удаляем уведомления
            await db.execute(f"DELETE FROM notifications WHERE user_id IN ({','.join(map(str, user_ids))})")
            
            # Удаляем оценки
            await db.execute(f"DELETE FROM grades WHERE student_id IN ({','.join(map(str, user_ids))})")
            
            # Удаляем записи о посещаемости
            await db.execute(f"DELETE FROM attendance WHERE student_id IN ({','.join(map(str, user_ids))})")
            
            # Удаляем самих пользователей
            await db.execute(f"DELETE FROM users WHERE telegram_id IN ({','.join(map(str, user_ids))})")
            
            # Сохраняем изменения
            await db.commit()
            
            print(f"Пользователи с ID {', '.join(map(str, user_ids))} успешно удалены!")
            print("Теперь вы можете заново зарегистрировать этих пользователей в боте.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(delete_test_users())

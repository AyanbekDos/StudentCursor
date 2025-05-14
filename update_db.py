import asyncio
import aiosqlite
import sys
from config import DATABASE_PATH

# Устанавливаем кодировку для вывода в консоль
sys.stdout.reconfigure(encoding='utf-8')

async def update_database():
    """Обновляет структуру базы данных, добавляя недостающие столбцы"""
    
    print("Начинаю обновление базы данных...")
    
    try:
        # Подключаемся к базе данных
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Проверяем, есть ли столбец notification_type в таблице notifications
            db.row_factory = aiosqlite.Row
            async with db.execute("PRAGMA table_info(notifications)") as cursor:
                columns = await cursor.fetchall()
                column_names = [column['name'] for column in columns]
                
                if 'notification_type' not in column_names:
                    print("Столбец notification_type отсутствует в таблице notifications. Добавляю...")
                    await db.execute("ALTER TABLE notifications ADD COLUMN notification_type TEXT DEFAULT 'general'")
                    await db.commit()
                    print("Столбец notification_type успешно добавлен!")
                else:
                    print("Столбец notification_type уже существует в таблице notifications.")
            
            print("\nОбновление базы данных завершено успешно!")
            
    except Exception as e:
        print(f"Произошла ошибка при обновлении базы данных: {e}")

if __name__ == "__main__":
    asyncio.run(update_database())

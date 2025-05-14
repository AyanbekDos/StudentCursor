import logging
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, DATABASE_PATH
from database.db import db
from modules import registration, schedule, grades, notifications, attendance
from modules.keyboards import BUTTON_COMMANDS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание экземпляров бота и диспетчера
def setup_bot():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    
    # Регистрация обработчиков из модулей
    registration.register_handlers(dp)
    schedule.register_handlers(dp)
    grades.register_handlers(dp)
    notifications.register_handlers(dp)
    attendance.register_handlers(dp)
    
    # Обработчики для кнопок меню
    @dp.message_handler(lambda message: message.text == "📊 Расписание")
    async def schedule_button_handler(message: types.Message):
        # Перенаправляем на команду /schedule
        state = dp.current_state(user=message.from_user.id)
        await schedule.cmd_schedule(message, state)
    
    @dp.message_handler(lambda message: message.text == "📝 Оценки" or message.text == "📝 Выставить оценки")
    async def grades_button_handler(message: types.Message):
        # Перенаправляем на команду /grades
        state = dp.current_state(user=message.from_user.id)
        await grades.cmd_grades(message, state)
    
    @dp.message_handler(lambda message: message.text == "🔔 Уведомления")
    async def notifications_button_handler(message: types.Message):
        # Перенаправляем на команду /notifications
        await notifications.cmd_notifications(message)
    
    @dp.message_handler(lambda message: message.text == "📸 Отметиться")
    async def checkin_button_handler(message: types.Message):
        # Перенаправляем на команду /checkin
        try:
            from modules.attendance import cmd_checkin
            state = dp.current_state(user=message.from_user.id)
            await cmd_checkin(message, state)
        except (ImportError, AttributeError):
            await message.answer("Функция отметки посещаемости недоступна.")
    
    @dp.message_handler(lambda message: message.text == "📋 Заявки")
    async def requests_button_handler(message: types.Message):
        # Перенаправляем на команду /requests
        try:
            from modules.registration import cmd_requests
            state = dp.current_state(user=message.from_user.id)
            await cmd_requests(message, state)
        except (ImportError, AttributeError):
            await message.answer("Функция просмотра заявок недоступна.")
    
    @dp.message_handler(lambda message: message.text == "👥 Управление группами")
    async def manage_groups_button_handler(message: types.Message):
        # Перенаправляем на команду /manage_groups
        try:
            from modules.registration import cmd_manage_groups
            state = dp.current_state(user=message.from_user.id)
            await cmd_manage_groups(message, state)
        except (ImportError, AttributeError):
            await message.answer("Функция управления группами недоступна.")
    
    @dp.message_handler(lambda message: message.text == "🔄 Создать QR-код")
    async def qr_button_handler(message: types.Message):
        # Перенаправляем на команду /qr
        try:
            from modules.attendance import cmd_qr
            state = dp.current_state(user=message.from_user.id)
            await cmd_qr(message, state)
        except (ImportError, AttributeError):
            await message.answer("Функция создания QR-кода недоступна.")
    
    # Обработчик для неизвестных команд и сообщений
    @dp.message_handler()
    async def unknown_message(message: types.Message):
        await message.answer(
            "Я не понимаю эту команду. Пожалуйста, используйте команды из меню."
        )
    
    return bot, dp

# Установка команд бота
async def set_commands(bot):
    commands = [
        BotCommand(command="/start", description="Начать работу с ботом"),
        BotCommand(command="/schedule", description="Расписание занятий"),
        BotCommand(command="/grades", description="Мои оценки"),
        BotCommand(command="/notifications", description="Уведомления"),
        BotCommand(command="/requests", description="Заявки на регистрацию (для преподавателей)"),
        BotCommand(command="/manage_groups", description="Управление группами (для преподавателей)"),
        BotCommand(command="/qr", description="Создать QR-код для отметки посещаемости (для преподавателей)")
    ]
    await bot.set_my_commands(commands)

# Функция запуска бота
async def on_startup(dispatcher):
    # Сброс webhook для предотвращения конфликтов
    await dispatcher.bot.delete_webhook(drop_pending_updates=True)
    
    # Инициализация базы данных
    try:
        await db.init()
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        sys.exit(1)
    
    # Установка команд бота
    bot = dispatcher.bot
    await set_commands(bot)
    logger.info("Бот успешно запущен")

# Точка входа
if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-fake-data":
        # Запускаем генерацию тестовых данных
        logger.info("Запуск генерации тестовых данных...")
        from modules.fake_data import run_fake_data_generation
        asyncio.run(run_fake_data_generation())
        logger.info("Команда генерации тестовых данных завершена")
    else:
        # Запускаем бота
        bot, dp = setup_bot()
        executor.start_polling(dp, on_startup=on_startup, skip_updates=True) 
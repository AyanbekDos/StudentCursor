# bot.py
import logging
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.dispatcher import FSMContext

from config import BOT_TOKEN, DATABASE_PATH
from database.db import db
from modules import registration, schedule, grades, notifications, attendance
from modules.keyboards import BUTTON_COMMANDS
from localization.kz_text import MESSAGES

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
    @dp.message_handler(lambda message: message.text == "📊 Сабақ кестесі", state="*")
    async def schedule_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /schedule
        current_state = dp.current_state(user=message.from_user.id)
        await schedule.cmd_schedule(message, current_state)
    
    @dp.message_handler(lambda message: message.text == "📝 Бағалар" or message.text == "📝 Баға қою", state="*")
    async def grades_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /grades
        current_state = dp.current_state(user=message.from_user.id)
        await grades.cmd_grades(message, current_state)
    
    @dp.message_handler(lambda message: message.text == "🔔 Хабарламалар", state="*")
    async def notifications_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /notifications
        await notifications.cmd_notifications(message)
    
    @dp.message_handler(lambda message: message.text == "📸 Белгілеу", state="*")
    async def checkin_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /checkin
        try:
            from modules.attendance import cmd_checkin
            current_state = dp.current_state(user=message.from_user.id)
            await cmd_checkin(message, current_state)
        except (ImportError, AttributeError):
            await message.answer("Қатысуды белгілеу функциясы қолжетімсіз.")
    
    @dp.message_handler(lambda message: message.text == "📋 Өтініштер", state="*")
    async def requests_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /requests
        try:
            from modules.registration import cmd_requests
            current_state = dp.current_state(user=message.from_user.id)
            await cmd_requests(message, current_state)
        except (ImportError, AttributeError):
            await message.answer("Өтініштерді қарау функциясы қолжетімсіз.")
    
    @dp.message_handler(lambda message: message.text == "👥 Топтарды басқару", state="*")
    async def manage_groups_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /manage_groups
        try:
            from modules.registration import cmd_manage_groups
            current_state = dp.current_state(user=message.from_user.id)
            await cmd_manage_groups(message, current_state)
        except (ImportError, AttributeError):
            await message.answer("Топтарды басқару функциясы қолжетімсіз.")
    
    @dp.message_handler(lambda message: message.text == "🔄 QR-код жасау", state="*")
    async def qr_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /qr
        try:
            from modules.attendance import cmd_qr
            current_state = dp.current_state(user=message.from_user.id)
            await cmd_qr(message, current_state)
        except (ImportError, AttributeError):
            await message.answer("QR-код жасау функциясы қолжетімсіз.")
    
    @dp.message_handler(lambda message: message.text == "🗑️ Профильді өшіру", state="*")
    async def delete_profile_button_handler(message: types.Message, state: FSMContext):
        # Сбрасываем текущее состояние
        await state.finish()
        # Перенаправляем на команду /delete_profile
        try:
            from modules.registration import cmd_delete_profile
            current_state = dp.current_state(user=message.from_user.id)
            await cmd_delete_profile(message, current_state)
        except (ImportError, AttributeError):
            await message.answer("Профильді өшіру функциясы қолжетімсіз.")
    
    # Обработчик для неизвестных команд и сообщений
    @dp.message_handler(state="*")
    async def unknown_message(message: types.Message, state: FSMContext):
        # Сбрасываем состояние для неизвестных сообщений
        current_state_name = await state.get_state()
        if current_state_name:
            logger.warning(f"Неизвестное сообщение в состоянии {current_state_name}: {message.text}")
            await state.finish()
        await message.answer(MESSAGES["unknown_command"])
    
    return bot, dp

# Установка команд бота
async def set_commands(bot):
    commands = [
        BotCommand(command="/start", description="Ботпен жұмысты бастау"),
        BotCommand(command="/schedule", description="Сабақ кестесі"),
        BotCommand(command="/grades", description="Менің бағаларым"),
        BotCommand(command="/notifications", description="Хабарламалар"),
        BotCommand(command="/requests", description="Тіркеуге өтініштер (оқытушылар үшін)"),
        BotCommand(command="/manage_groups", description="Топтарды басқару (оқытушылар үшін)"),
        BotCommand(command="/qr", description="Қатысуды белгілеу үшін QR-код жасау (оқытушылар үшін)"),
        BotCommand(command="/delete_profile", description="Профильді өшіру (студенттер үшін)")
    ]
    await bot.set_my_commands(commands)

# Функция запуска бота
async def on_startup(dispatcher):
    # Сброс webhook для предотвращения конфликтов
    await dispatcher.bot.delete_webhook(drop_pending_updates=True)
    
    # Инициализация базы данных
    try:
        await db.init()
        logger.info("Дерекқор сәтті инициализацияланды")
    except Exception as e:
        logger.error(f"Дерекқорды инициализациялауда қате: {e}")
        sys.exit(1)
    
    # Установка команд бота
    bot = dispatcher.bot
    await set_commands(bot)
    logger.info("Бот сәтті іске қосылды")

# Точка входа
if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-fake-data":
        # Запускаем генерацию тестовых данных
        logger.info("Тестілік деректерді генерациялау басталды...")
        from modules.fake_data import run_fake_data_generation
        asyncio.run(run_fake_data_generation())
        logger.info("Тестілік деректерді генерациялау командасы аяқталды")
    else:
        # Запускаем бота
        bot, dp = setup_bot()
        executor.start_polling(dp, on_startup=on_startup, skip_updates=True)

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
import asyncio
from flask import Flask, request
import threading
import sys

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Данные о типах заявок (ваша существующая структура) ---
APPLICATION_TYPES = {
    '1': {
        'name': 'Вызов представителей и специалистов Заказчика',
        'submission_time': 12,
        'confirm_time': 2,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'Допускается для переноса выезда партии по времени заявки, но не более чем на 4 часа'
    },
    # ... (остальные типы заявок остаются без изменений)
    '16': {
        'name': 'На бульдозерную технику Заказчика',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    }
}

# Состояния пользователя
user_data = {}

# --- Обработчики команд (ваши существующие обработчики) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
        [InlineKeyboardButton("📋 Список типов заявок", callback_data='list_applications')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '👋 Добро пожаловать в бот для подачи заявок!\n\n'
        'Выберите действие:',
        reply_markup=reply_markup
    )

# ... (все ваши существующие обработчики остаются без изменений)
# Я не копирую их все сюда для краткости, но вы оставляете свои функции

# --- Flask сервер для Render ---
app = Flask(__name__)

# Глобальная переменная для бота
bot_application = None

def create_application():
    """Создает и настраивает Application"""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не найден")
        return None
    
    # Создаем Application
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!back_to_main$).*'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

@app.route('/')
def home():
    return "Бот работает! Версия: 1.0"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    global bot_application
    
    if bot_application is None:
        bot_application = create_application()
        if bot_application is None:
            return "Bot not initialized", 500
    
    try:
        # Получаем обновление от Telegram
        update_data = request.get_json()
        logger.info(f"Получено обновление: {update_data.get('update_id')}")
        
        # Создаем объект Update
        update = Update.de_json(update_data, bot_application.bot)
        
        # Обрабатываем обновление
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_application.process_update(update))
        loop.close()
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Ошибка обработки обновления: {e}")
        return 'Error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Устанавливает вебхук"""
    global bot_application
    
    if bot_application is None:
        bot_application = create_application()
    
    if bot_application is None:
        return "Bot not initialized", 500
    
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        return "RENDER_EXTERNAL_URL не найден", 500
    
    full_webhook_url = f"{webhook_url}/webhook"
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_application.bot.set_webhook(full_webhook_url))
        loop.close()
        
        return f"Webhook установлен на {full_webhook_url}"
    except Exception as e:
        return f"Ошибка: {e}", 500

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """Удаляет вебхук"""
    global bot_application
    
    if bot_application is None:
        bot_application = create_application()
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_application.bot.delete_webhook())
        loop.close()
        
        return "Webhook удален"
    except Exception as e:
        return f"Ошибка: {e}", 500

@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """Информация о вебхуке"""
    global bot_application
    
    if bot_application is None:
        bot_application = create_application()
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        info = loop.run_until_complete(bot_application.bot.get_webhook_info())
        loop.close()
        
        return f"""
        <h1>Информация о вебхуке</h1>
        <p>URL: {info.url}</p>
        <p>Ожидающие обновления: {info.pending_update_count}</p>
        <p>Макс. соединений: {info.max_connections}</p>
        """
    except Exception as e:
        return f"Ошибка: {e}", 500

# --- Точка входа ---
if __name__ == '__main__':
    # Инициализируем бота
    bot_application = create_application()
    
    if bot_application is None:
        logger.error("Не удалось инициализировать бота")
        sys.exit(1)
    
    # Автоматически устанавливаем вебхук
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        full_webhook_url = f"{webhook_url}/webhook"
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(bot_application.bot.set_webhook(full_webhook_url))
            loop.close()
            logger.info(f"Вебхук установлен на {full_webhook_url}")
        except Exception as e:
            logger.error(f"Ошибка установки вебхука: {e}")
    else:
        logger.warning("RENDER_EXTERNAL_URL не найден, вебхук не установлен")
    
    # Запускаем Flask сервер
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Запуск Flask сервера на порту {port}")
    app.run(host="0.0.0.0", port=port)
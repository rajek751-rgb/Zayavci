import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import re
import os
import asyncio
from flask import Flask, request
import threading

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ВАША ОСНОВНАЯ ЛОГИКА БОТА (ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ) ---
# Данные о типах заявок из предоставленной таблицы
APPLICATION_TYPES = {
    '1': {
        'name': 'Вызов представителей и специалистов Заказчика',
        'submission_time': 12,
        'confirm_time': 2,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'Допускается для переноса выезда партии по времени заявки, но не более чем на 4 часа'
    },
    '2': {
        'name': 'ГИРС (ПВР)',
        'submission_time': 16,
        'confirm_time': '12 и 2 (4*)',
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'note': 'В случае, если скважина находится более 100км, то второе подтверждение за 4 часа. С соблюдением требований п. 5.7 регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту оборудования УЭПН'
    },
    '3': {
        'name': 'Монтаж/демонтаж УЭЦН',
        'submission_time': 24,
        'confirm_time': '12 и 2 (4*)',
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'note': 'С соблюдением требований п. 5.7 регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту оборудования УЭПН'
    },
    '4': {
        'name': 'Проведение ОПЗ (СКО, ГКО)',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'менее чем за 6 часов',
        'note': 'Первичная заявка подаётся за 3 суток, с направлением информации по скважине для формирования спец.плана на производство РИР'
    },
    '5': {
        'name': 'Проведение РИР (ЛНЭК)',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 6 часов',
        'note': 'С соблюдением требований регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту глубино-насосного оборудования (ГНО)'
    },
    '6': {
        'name': 'Завоз/вывоз НКТ, ШН',
        'submission_time': 'до 15 часов рабочего дня предшествующего дню завоза/вывоза',
        'confirm_time': 'с 8 до 9 часов утра дня завоза/вывоза',
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'С соблюдением требований регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту глубино-насосного оборудования (ГНО)'
    },
    '7': {
        'name': 'Завоз/вывоз паверных устройств',
        'submission_time': 24,
        'confirm_time': 4,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'С соблюдением требований регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту глубино-насосного оборудования (ГНО)'
    },
    '8': {
        'name': 'Завоз/вывоз промыслового оборудования',
        'submission_time': 24,
        'confirm_time': 4,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'С соблюдением требований регламента бизнес-процесса ООО "Башнефть-Добыча" По движению и учёту глубино-насосного оборудования (ГНО)'
    },
    '9': {
        'name': 'Предоставление и завоз нефти для технологических операций',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': ''
    },
    '10': {
        'name': 'Приготовление и отпуск технологической жидкости',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 6 часов',
        'note': ''
    },
    '11': {
        'name': 'Завоз/вывоз оборудования ГРП',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'С подтверждением в день завоза/вывоза до 7:00 (минимум за 12 часов)'
    },
    '12': {
        'name': 'Вызов представителя ГРП',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': ''
    },
    '13': {
        'name': 'Монтаж/демонтаж ШСНУ',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'Договора по обслуживанию ШГН'
    },
    '14': {
        'name': 'Завоз жидкости ГРП',
        'submission_time': 24,
        'confirm_time': 6,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'note': ''
    },
    '15': {
        'name': 'Вызов представителей и специалистов БВО',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': 'Опрессовка колонн и ПВО, выдача разрешений на выполнение работ на скважинах 1 категории опасности по ГНВП (подача, перенос и подтверждение заявок осуществляет посредством электронной почты)'
    },
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_application':
        await show_application_types(query)
    elif query.data == 'list_applications':
        await show_all_applications(query)
    elif query.data == 'help':
        await show_help(query)
    elif query.data.startswith('select_type_'):
        app_type = query.data.replace('select_type_', '')
        await start_application_creation(query, app_type)
    elif query.data == 'confirm_application':
        await confirm_application(query)
    elif query.data == 'cancel_application':
        await cancel_application(query)
    elif query.data == 'back_to_types':
        await show_application_types(query)
    elif query.data.startswith('transfer1_'):
        await handle_transfer(query, 1)
    elif query.data.startswith('transfer2_'):
        await handle_transfer(query, 2)

async def show_application_types(query):
    """Показать список типов заявок для выбора"""
    keyboard = []
    for key, value in APPLICATION_TYPES.items():
        keyboard.append([InlineKeyboardButton(
            f"{key}. {value['name']}", 
            callback_data=f'select_type_{key}'
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        'Выберите тип заявки:',
        reply_markup=reply_markup
    )

async def show_all_applications(query):
    """Показать все типы заявок с описанием"""
    text = "📋 **Все типы заявок:**\n\n"
    
    for key, value in APPLICATION_TYPES.items():
        text += f"**{key}. {value['name']}**\n"
        text += f"⏰ Подача: за {value['submission_time']} ч.\n"
        text += f"✅ Подтверждение: за {value['confirm_time']} ч.\n"
        
        if value.get('transfer1_allowed') or value.get('transfer2_allowed'):
            transfers = []
            if value['transfer1_allowed']:
                transfers.append("1-й перенос разрешен")
            if value['transfer2_allowed']:
                transfers.append("2-й перенос разрешен")
            text += f"🔄 {', '.join(transfers)}\n"
        
        if value['note']:
            text += f"📌 Примечание: {value['note']}\n"
        text += "\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_help(query):
    """Показать справку"""
    help_text = (
        "❓ **Помощь по использованию бота:**\n\n"
        "1️⃣ Для создания новой заявки нажмите 'Создать новую заявку'\n"
        "2️⃣ Выберите тип заявки из списка\n"
        "3️⃣ Заполните необходимые данные:\n"
        "   • Месторождение\n"
        "   • Номер бригады\n"
        "   • Желаемое время выполнения\n"
        "4️⃣ Бот проверит соответствие времени подачи требованиям\n"
        "5️⃣ При необходимости можно сделать перенос заявки\n\n"
        "📌 Все заявки должны подаваться с учетом времени, указанного в регламенте"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def start_application_creation(query, app_type):
    """Начать создание заявки выбранного типа"""
    user_id = query.from_user.id
    user_data[user_id] = {
        'type': app_type,
        'step': 'field',
        'data': {}
    }
    
    app_info = APPLICATION_TYPES[app_type]
    
    info_text = (
        f"📝 **Создание заявки: {app_info['name']}**\n\n"
        f"⏰ **Требования:**\n"
        f"• Подача заявки: за {app_info['submission_time']} ч.\n"
        f"• Подтверждение: за {app_info['confirm_time']} ч.\n"
    )
    
    if app_info.get('transfer1_allowed') or app_info.get('transfer2_allowed'):
        info_text += "🔄 **Переносы:** Разрешены\n"
    
    if app_info['note']:
        info_text += f"\n📌 **Примечание:** {app_info['note']}\n"
    
    info_text += "\nВведите название месторождения:"
    
    await query.edit_message_text(
        info_text,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.message.from_user.id
    text = update.message.text
    
    if user_id not in user_data:
        await update.message.reply_text(
            "Пожалуйста, начните с команды /start"
        )
        return
    
    step = user_data[user_id]['step']
    app_type = user_data[user_id]['type']
    app_info = APPLICATION_TYPES[app_type]
    
    if step == 'field':
        user_data[user_id]['data']['field'] = text
        user_data[user_id]['step'] = 'brigade'
        await update.message.reply_text("Введите номер бригады:")
        
    elif step == 'brigade':
        user_data[user_id]['data']['brigade'] = text
        user_data[user_id]['step'] = 'execution_time'
        await update.message.reply_text(
            "Введите желаемое время выполнения (в формате ДД.ММ.ГГГГ ЧЧ:ММ):"
        )
        
    elif step == 'execution_time':
        try:
            execution_time = datetime.strptime(text, '%d.%m.%Y %H:%M')
            current_time = datetime.now()
            
            # Проверка времени подачи
            time_diff = execution_time - current_time
            hours_diff = time_diff.total_seconds() / 3600
            
            submission_time = app_info['submission_time']
            if isinstance(submission_time, int):
                if hours_diff < submission_time:
                    warning = f"⚠️ Внимание! Заявка подается менее чем за {submission_time} часов до выполнения!"
                else:
                    warning = "✅ Время подачи соответствует требованиям"
            else:
                warning = f"ℹ️ Особые условия: {submission_time}"
            
            user_data[user_id]['data']['execution_time'] = text
            user_data[user_id]['step'] = 'review'
            
            # Показываем сводку и предлагаем подтвердить или перенести
            await show_application_review(update, user_id, app_info, warning)
            
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ"
            )
    elif step.startswith('transfer_'):
        # Обработка переноса (упрощенно)
        try:
            new_time = datetime.strptime(text, '%d.%m.%Y %H:%M')
            user_data[user_id]['data']['execution_time'] = text
            user_data[user_id]['step'] = 'review'
            warning = f"🔄 Время перенесено на {text}"
            await show_application_review(update, user_id, app_info, warning)
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ"
            )

async def show_application_review(update, user_id, app_info, warning):
    """Показать сводку заявки и предложить действия"""
    data = user_data[user_id]['data']
    
    review_text = (
        f"📋 **Проверьте данные заявки:**\n\n"
        f"**Тип:** {app_info['name']}\n"
        f"**Месторождение:** {data['field']}\n"
        f"**Номер бригады:** {data['brigade']}\n"
        f"**Время выполнения:** {data['execution_time']}\n\n"
        f"{warning}\n\n"
        f"Выберите действие:"
    )
    
    keyboard = []
    
    # Кнопки переноса, если разрешены
    if app_info.get('transfer1_allowed'):
        keyboard.append([InlineKeyboardButton(
            "🔄 Сделать 1-й перенос", 
            callback_data=f'transfer1_{user_id}'
        )])
    
    if app_info.get('transfer2_allowed'):
        keyboard.append([InlineKeyboardButton(
            "🔄 Сделать 2-й перенос", 
            callback_data=f'transfer2_{user_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("✅ Подтвердить заявку", callback_data='confirm_application')])
    keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data='cancel_application')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        review_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_transfer(query, transfer_number):
    """Обработка переноса заявки"""
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Сессия истекла. Начните заново с /start")
        return
    
    app_type = user_data[user_id]['type']
    app_info = APPLICATION_TYPES[app_type]
    
    transfer_note = app_info.get('transfer_note', '')
    note_text = f" ({transfer_note})" if transfer_note else ""
    
    await query.edit_message_text(
        f"🔄 **Перенос #{transfer_number} заявки**{note_text}\n\n"
        f"Введите новое время выполнения (в формате ДД.ММ.ГГГГ ЧЧ:ММ):"
    )
    
    user_data[user_id]['step'] = f'transfer_{transfer_number}'

async def confirm_application(query):
    """Подтверждение и сохранение заявки"""
    user_id = query.from_user.id
    
    if user_id not in user_data:
        await query.edit_message_text("Сессия истекла. Начните заново с /start")
        return
    
    data = user_data[user_id]['data']
    app_type = user_data[user_id]['type']
    app_info = APPLICATION_TYPES[app_type]
    
    # Здесь можно добавить сохранение в базу данных или отправку уведомления
    
    success_text = (
        f"✅ **Заявка успешно создана!**\n\n"
        f"**Тип:** {app_info['name']}\n"
        f"**Месторождение:** {data['field']}\n"
        f"**Номер бригады:** {data['brigade']}\n"
        f"**Время выполнения:** {data['execution_time']}\n\n"
        f"Не забудьте подтвердить заявку за {app_info['confirm_time']} часов до выполнения."
    )
    
    keyboard = [[InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        success_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Очищаем данные пользователя
    del user_data[user_id]

async def cancel_application(query):
    """Отмена создания заявки"""
    user_id = query.from_user.id
    
    if user_id in user_data:
        del user_data[user_id]
    
    keyboard = [[InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "❌ Создание заявки отменено.",
        reply_markup=reply_markup
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
        [InlineKeyboardButton("📋 Список типов заявок", callback_data='list_applications')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        '👋 Главное меню:\n\nВыберите действие:',
        reply_markup=reply_markup
    )

# --- НОВАЯ ЧАСТЬ: НАСТРОЙКА ВЕБХУКА ---

# Создаем Flask приложение
app = Flask(__name__)

# Глобальная переменная для хранения экземпляра Application
telegram_app = None

def init_telegram_app():
    """Инициализация Telegram приложения"""
    global telegram_app
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения")
        return None
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!back_to_main$).*'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    if telegram_app is None:
        return "Bot not initialized", 500
    
    try:
        update = Update.de_json(request.get_json(), telegram_app.bot)
        asyncio.run(telegram_app.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return 'Error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Ручная установка вебхука (можно вызвать через браузер)"""
    try:
        webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not webhook_url:
            return "RENDER_EXTERNAL_URL not set", 500
        
        full_webhook_url = f"{webhook_url}/webhook"
        
        if telegram_app is None:
            return "Bot not initialized", 500
        
        # Устанавливаем вебхук
        asyncio.run(telegram_app.bot.set_webhook(full_webhook_url))
        
        # Проверяем информацию о вебхуке
        webhook_info = asyncio.run(telegram_app.bot.get_webhook_info())
        
        return f"""
        <h1>Webhook установлен!</h1>
        <p>URL: {webhook_info.url}</p>
        <p>Ожидающие обновления: {webhook_info.pending_update_count}</p>
        <p>Макс. соединений: {webhook_info.max_connections}</p>
        """
    except Exception as e:
        return f"Error setting webhook: {e}", 500

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """Удаление вебхука"""
    try:
        if telegram_app is None:
            return "Bot not initialized", 500
        
        asyncio.run(telegram_app.bot.delete_webhook())
        return "Webhook удален!"
    except Exception as e:
        return f"Error deleting webhook: {e}", 500

@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """Информация о текущем вебхуке"""
    try:
        if telegram_app is None:
            return "Bot not initialized", 500
        
        webhook_info = asyncio.run(telegram_app.bot.get_webhook_info())
        return f"""
        <h1>Информация о вебхуке</h1>
        <p>URL: {webhook_info.url}</p>
        <p>Ожидающие обновления: {webhook_info.pending_update_count}</p>
        <p>Последняя ошибка: {webhook_info.last_error_message}</p>
        <p>Макс. соединений: {webhook_info.max_connections}</p>
        """
    except Exception as e:
        return f"Error getting webhook info: {e}", 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    # Инициализируем Telegram бота
    telegram_app = init_telegram_app()
    
    if telegram_app is None:
        logger.error("Не удалось инициализировать бота. Проверьте TELEGRAM_TOKEN")
        exit(1)
    
    # Автоматически устанавливаем вебхук при запуске
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if webhook_url:
        full_webhook_url = f"{webhook_url}/webhook"
        try:
            asyncio.run(telegram_app.bot.set_webhook(full_webhook_url))
            logger.info(f"Webhook установлен на {full_webhook_url}")
            
            # Проверяем установку
            webhook_info = asyncio.run(telegram_app.bot.get_webhook_info())
            logger.info(f"Информация о вебхуке: {webhook_info.url}")
        except Exception as e:
            logger.error(f"Ошибка установки вебхука: {e}")
    else:
        logger.warning("RENDER_EXTERNAL_URL не найден, вебхук не установлен автоматически")
    
    # Запускаем Flask сервер (Render будет использовать этот порт)
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Запуск Flask сервера на порту {port}")
    app.run(host="0.0.0.0", port=port)
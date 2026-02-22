import logging
import smtplib
import os
import sys
import asyncio
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Состояния для ConversationHandler ---
SELECTING_TYPE, ENTERING_DATE, ENTERING_TIME, ENTERING_DESC, ENTERING_ADDRESS, CONFIRMING = range(6)

# --- Данные о типах заявок (полная структура) ---
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
        'name': 'Вызов скорой помощи для работников',
        'submission_time': 0,
        'confirm_time': 0,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'Круглосуточно'
    },
    '3': {
        'name': 'На пожарную машину',
        'submission_time': 0,
        'confirm_time': 0,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': 'Круглосуточно'
    },
    '4': {
        'name': 'На поливомоечную машину',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': False,
        'transfer2_allowed': False,
        'note': ''
    },
    '5': {
        'name': 'На кран',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '6': {
        'name': 'На погрузчик',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '7': {
        'name': 'На самосвал',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '8': {
        'name': 'На автосамосвал',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '9': {
        'name': 'На трал',
        'submission_time': 48,
        'confirm_time': 24,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 24 часа',
        'note': 'погрузка негабаритного груза'
    },
    '10': {
        'name': 'На кран',
        'submission_time': 48,
        'confirm_time': 24,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 24 часа',
        'note': 'монтаж'
    },
    '11': {
        'name': 'На автовышку',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '12': {
        'name': 'На кран',
        'submission_time': 48,
        'confirm_time': 24,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 24 часа',
        'note': 'ст монтаж'
    },
    '13': {
        'name': 'На поливомоечную машину',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '14': {
        'name': 'На тракторную технику Заказчика',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
    },
    '15': {
        'name': 'На бульдозерную технику Заказчика',
        'submission_time': 24,
        'confirm_time': 12,
        'transfer1_allowed': True,
        'transfer2_allowed': True,
        'transfer_note': 'за 12 часов',
        'note': ''
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

# --- Настройки email ---
SMTP_SERVER = "smtp.gmail.com"  # Для Gmail, для других почт измените
SMTP_PORT = 587
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "your-email@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your-app-password")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin-email@gmail.com")

# ID для уведомлений в Telegram
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "YOUR_CHAT_ID")  # ID чата админа
NOTIFICATION_GROUP_ID = os.environ.get("NOTIFICATION_GROUP_ID", "YOUR_GROUP_ID")  # ID группы для уведомлений

# --- Хранилище данных пользователей ---
user_data_store = {}

# --- Вспомогательные функции ---
def get_application_type_name(type_id):
    """Получить название типа заявки по ID"""
    return APPLICATION_TYPES.get(type_id, {}).get('name', 'Неизвестный тип')

def validate_date_time(date_str, time_str, type_id):
    """Проверка даты и времени подачи заявки"""
    try:
        # Парсим дату и время
        submission_datetime = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        now = datetime.now()
        
        # Получаем требуемое время подачи для этого типа заявки
        submission_hours = APPLICATION_TYPES.get(type_id, {}).get('submission_time', 0)
        
        if submission_hours == 0:
            # Можно подавать в любое время
            return True, None
        
        # Вычисляем минимальное допустимое время
        min_allowed_time = now + timedelta(hours=submission_hours)
        
        if submission_datetime < min_allowed_time:
            return False, f"Заявки этого типа принимаются минимум за {submission_hours} часов до требуемого времени"
        
        return True, None
    except Exception as e:
        return False, f"Ошибка при проверке даты: {e}"

def send_email_notification(application_data):
    """Отправка уведомления на email"""
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = f"Новая заявка #{application_data.get('id', 'N/A')}"
        
        # Формируем тело письма
        body = f"""
        Новая заявка в системе
        
        Номер заявки: {application_data.get('id', 'N/A')}
        Тип заявки: {application_data.get('type_name', 'N/A')}
        
        Дата и время: {application_data.get('date', 'N/A')} {application_data.get('time', 'N/A')}
        Адрес/Место: {application_data.get('address', 'N/A')}
        
        Описание работ:
        {application_data.get('description', 'N/A')}
        
        Контактные данные:
        Пользователь: {application_data.get('user_name', 'N/A')}
        Username: @{application_data.get('username', 'N/A')}
        User ID: {application_data.get('user_id', 'N/A')}
        
        Время создания: {application_data.get('created_at', 'N/A')}
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Отправляем письмо
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email уведомление отправлено для заявки #{application_data.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        return False

async def send_telegram_notification(application_data):
    """Отправка уведомления в Telegram"""
    try:
        # Формируем сообщение
        message = f"""
📋 **НОВАЯ ЗАЯВКА** #{application_data.get('id', 'N/A')}

🔹 **Тип:** {application_data.get('type_name', 'N/A')}
🔹 **Дата/время:** {application_data.get('date', 'N/A')} {application_data.get('time', 'N/A')}
🔹 **Адрес:** {application_data.get('address', 'N/A')}

📝 **Описание:**
{application_data.get('description', 'N/A')}

👤 **Отправитель:** {application_data.get('user_name', 'N/A')} (@{application_data.get('username', 'N/A')})
🆔 **User ID:** {application_data.get('user_id', 'N/A')}

⏱ **Создано:** {application_data.get('created_at', 'N/A')}
        """
        
        # Отправляем админу
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "YOUR_CHAT_ID":
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
        
        # Отправляем в группу
        if NOTIFICATION_GROUP_ID and NOTIFICATION_GROUP_ID != "YOUR_GROUP_ID":
            await context.bot.send_message(
                chat_id=NOTIFICATION_GROUP_ID,
                text=message,
                parse_mode='Markdown'
            )
        
        logger.info(f"Telegram уведомление отправлено для заявки #{application_data.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки Telegram уведомления: {e}")
        return False

def generate_application_id():
    """Генерация уникального номера заявки"""
    now = datetime.now()
    return f"APP-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
        [InlineKeyboardButton("📋 Список типов заявок", callback_data='list_applications')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сохраняем информацию о пользователе
    user_id = update.effective_user.id
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            'name': update.effective_user.full_name,
            'username': update.effective_user.username,
            'applications': []
        }
    
    await update.message.reply_text(
        '👋 Добро пожаловать в бот для подачи заявок!\n\n'
        'Выберите действие:',
        reply_markup=reply_markup
    )

async def list_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех типов заявок"""
    query = update.callback_query
    await query.answer()
    
    message = "📋 *Список типов заявок:*\n\n"
    
    for type_id, type_info in APPLICATION_TYPES.items():
        message += f"*{type_id}.* {type_info['name']}\n"
        message += f"   ⏱ Подача: за {type_info['submission_time']} ч\n"
        if type_info.get('note'):
            message += f"   📌 {type_info['note']}\n"
        message += "\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку"""
    query = update.callback_query
    await query.answer()
    
    help_text = """
❓ *Помощь по использованию бота*

*Как создать заявку:*
1. Нажмите "Создать новую заявку"
2. Выберите тип заявки
3. Введите дату (ДД.ММ.ГГГГ)
4. Введите время (ЧЧ:ММ)
5. Опишите работы
6. Укажите адрес/место
7. Подтвердите заявку

*Важно:* 
- Время подачи зависит от типа заявки
- Некоторые заявки принимаются круглосуточно
- Заявки можно создавать за несколько дней

*Контакты поддержки:*
@admin
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
        [InlineKeyboardButton("📋 Список типов заявок", callback_data='list_applications')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')],
        [InlineKeyboardButton("📊 Мои заявки", callback_data='my_applications')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        '👋 Выберите действие:',
        reply_markup=reply_markup
    )

async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заявки пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_apps = user_data_store.get(user_id, {}).get('applications', [])
    
    if not user_apps:
        text = "У вас пока нет заявок"
    else:
        text = "📊 *Ваши заявки:*\n\n"
        for i, app in enumerate(user_apps[-5:], 1):  # Показываем последние 5
            text += f"*{i}. Заявка #{app['id']}*\n"
            text += f"📅 {app['date']} {app['time']}\n"
            text += f"📝 {app['type_name'][:30]}...\n"
            text += f"📍 {app['address'][:30]}...\n"
            text += f"✅ Статус: {app.get('status', 'Принята')}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# --- Обработчики создания заявки ---
async def new_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание новой заявки"""
    query = update.callback_query
    await query.answer()
    
    # Создаем клавиатуру с типами заявок (по 2 в ряд)
    keyboard = []
    row = []
    
    for i, (type_id, type_info) in enumerate(APPLICATION_TYPES.items(), 1):
        button = InlineKeyboardButton(
            f"{type_id}. {type_info['name'][:20]}", 
            callback_data=f"select_type_{type_id}"
        )
        row.append(button)
        
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    
    if row:  # Добавляем оставшиеся кнопки
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите тип заявки:",
        reply_markup=reply_markup
    )
    
    return SELECTING_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа заявки"""
    query = update.callback_query
    await query.answer()
    
    type_id = query.data.replace('select_type_', '')
    context.user_data['application_type'] = type_id
    context.user_data['application_type_name'] = APPLICATION_TYPES[type_id]['name']
    
    type_info = APPLICATION_TYPES[type_id]
    submission_time = type_info['submission_time']
    
    if submission_time == 0:
        time_note = "✅ Можно подавать в любое время"
    else:
        time_note = f"⏱ Минимальное время подачи: за {submission_time} ч"
    
    await query.edit_message_text(
        f"Вы выбрали: *{type_info['name']}*\n\n"
        f"{time_note}\n\n"
        f"📅 Введите дату в формате ДД.ММ.ГГГГ\n"
        f"Например: 25.12.2024",
        parse_mode='Markdown'
    )
    
    return ENTERING_DATE

async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода даты"""
    date_str = update.message.text.strip()
    
    # Проверка формата даты
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        context.user_data['application_date'] = date_str
        
        await update.message.reply_text(
            f"📅 Дата: {date_str}\n\n"
            f"⏰ Теперь введите время в формате ЧЧ:ММ\n"
            f"Например: 14:30"
        )
        return ENTERING_TIME
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 25.12.2024"
        )
        return ENTERING_DATE

async def enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода времени"""
    time_str = update.message.text.strip()
    
    # Проверка формата времени
    try:
        datetime.strptime(time_str, "%H:%M")
        
        # Проверяем допустимость даты и времени
        date_str = context.user_data.get('application_date')
        type_id = context.user_data.get('application_type')
        
        is_valid, error_msg = validate_date_time(date_str, time_str, type_id)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                f"Пожалуйста, введите другую дату:"
            )
            return ENTERING_DATE
        
        context.user_data['application_time'] = time_str
        
        await update.message.reply_text(
            f"📝 Введите описание работ:"
        )
        return ENTERING_DESC
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ\n"
            "Например: 14:30"
        )
        return ENTERING_TIME

async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода описания"""
    description = update.message.text.strip()
    
    if len(description) < 10:
        await update.message.reply_text(
            "❌ Описание слишком короткое. Пожалуйста, опишите работы подробнее (минимум 10 символов):"
        )
        return ENTERING_DESC
    
    context.user_data['application_description'] = description
    
    await update.message.reply_text(
        f"📍 Введите адрес или место проведения работ:"
    )
    return ENTERING_ADDRESS

async def enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода адреса"""
    address = update.message.text.strip()
    
    if len(address) < 5:
        await update.message.reply_text(
            "❌ Адрес слишком короткий. Пожалуйста, укажите более точный адрес:"
        )
        return ENTERING_ADDRESS
    
    context.user_data['application_address'] = address
    
    # Показываем сводку для подтверждения
    summary = (
        f"📋 *Проверьте данные заявки:*\n\n"
        f"🔹 *Тип:* {context.user_data['application_type_name']}\n"
        f"🔹 *Дата:* {context.user_data['application_date']}\n"
        f"🔹 *Время:* {context.user_data['application_time']}\n"
        f"🔹 *Адрес:* {address}\n"
        f"🔹 *Описание:* {context.user_data['application_description']}\n\n"
        f"✅ Всё верно?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, отправить", callback_data='confirm_yes'),
            InlineKeyboardButton("❌ Нет, заново", callback_data='confirm_no')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        summary,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return CONFIRMING

async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и отправка заявки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'confirm_yes':
        # Формируем данные заявки
        user = query.from_user
        now = datetime.now()
        
        application_data = {
            'id': generate_application_id(),
            'user_id': user.id,
            'user_name': user.full_name,
            'username': user.username,
            'type_id': context.user_data['application_type'],
            'type_name': context.user_data['application_type_name'],
            'date': context.user_data['application_date'],
            'time': context.user_data['application_time'],
            'description': context.user_data['application_description'],
            'address': context.user_data['application_address'],
            'created_at': now.strftime("%d.%m.%Y %H:%M:%S"),
            'status': 'Принята'
        }
        
        # Сохраняем в историю пользователя
        user_id = user.id
        if user_id not in user_data_store:
            user_data_store[user_id] = {'applications': []}
        user_data_store[user_id]['applications'].append(application_data)
        
        # Отправляем уведомления
        send_email_notification(application_data)
        await send_telegram_notification(application_data)
        
        # Отправляем подтверждение пользователю
        await query.edit_message_text(
            f"✅ *Заявка #{application_data['id']} успешно отправлена!*\n\n"
            f"Мы получили вашу заявку и скоро свяжемся с вами.\n\n"
            f"📋 *Детали заявки:*\n"
            f"🔹 Тип: {application_data['type_name']}\n"
            f"🔹 Дата/время: {application_data['date']} {application_data['time']}\n"
            f"🔹 Адрес: {application_data['address']}\n\n"
            f"💾 Номер заявки сохранен, вы можете ссылаться на него при общении.",
            parse_mode='Markdown'
        )
        
        # Очищаем временные данные
        context.user_data.clear()
        
        # Показываем главное меню
        keyboard = [
            [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
            [InlineKeyboardButton("📋 Мои заявки", callback_data='my_applications')],
            [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "Что делаем дальше?",
            reply_markup=reply_markup
        )
    else:
        # Отмена и возврат к выбору типа
        context.user_data.clear()
        
        # Создаем клавиатуру с типами заявок
        keyboard = []
        row = []
        
        for i, (type_id, type_info) in enumerate(APPLICATION_TYPES.items(), 1):
            button = InlineKeyboardButton(
                f"{type_id}. {type_info['name'][:20]}", 
                callback_data=f"select_type_{type_id}"
            )
            row.append(button)
            
            if i % 2 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Давайте начнем заново. Выберите тип заявки:",
            reply_markup=reply_markup
        )
        
        return SELECTING_TYPE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия"""
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать новую заявку", callback_data='new_application')],
        [InlineKeyboardButton("🔙 В главное меню", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❌ Действие отменено. Выберите действие:",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

# --- Основной обработчик кнопок ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки (не входящие в Conversation)"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_application':
        # Запускаем создание заявки через ConversationHandler
        return await new_application(update, context)
    elif query.data == 'list_applications':
        await list_applications(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'my_applications':
        await my_applications(update, context)
    elif query.data.startswith('select_type_'):
        return await select_type(update, context)
    
    return ConversationHandler.END

# --- Настройка и запуск бота ---
def create_application():
    """Создает и настраивает Application"""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения")
        return None
    
    # Создаем Application
    application = Application.builder().token(token).build()
    
    # Создаем ConversationHandler для создания заявки
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_application, pattern='^new_application$')],
        states={
            SELECTING_TYPE: [
                CallbackQueryHandler(select_type, pattern='^select_type_')
            ],
            ENTERING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            ENTERING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_time)],
            ENTERING_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description)],
            ENTERING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_address)],
            CONFIRMING: [CallbackQueryHandler(confirm_application, pattern='^(confirm_yes|confirm_no)$')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!new_application$|select_type_|confirm_|back_to_main$).*'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    
    # Добавляем обработчик для текстовых сообщений (если пользователь что-то пишет вне диалога)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений вне диалога"""
    await update.message.reply_text(
        "Я не понял команду. Используйте /start для начала работы."
    )

# --- Точка входа ---
if __name__ == '__main__':
    print("=" * 50)
    print("ЗАПУСК БОТА ДЛЯ ПРИЕМА ЗАЯВОК")
    print("=" * 50)
    
    # Проверяем наличие токена
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("❌ ОШИБКА: TELEGRAM_TOKEN не найден!")
        print("Установите переменную окружения TELEGRAM_TOKEN")
        sys.exit(1)
    
    # Проверяем настройки email (предупреждаем, но не останавливаем)
    if not EMAIL_ADDRESS or EMAIL_ADDRESS == "your-email@gmail.com":
        print("⚠️  ВНИМАНИЕ: EMAIL_ADDRESS не настроен, уведомления на почту работать не будут")
    
    # Создаем приложение бота
    application = create_application()
    
    if not application:
        print("❌ ОШИБКА: Не удалось создать приложение бота")
        sys.exit(1)
    
    print("✅ Бот успешно инициализирован")
    print("🚀 Запуск бота в режиме polling...")
    print("📝 Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    try:
        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        sys.exit(1)
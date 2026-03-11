import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = TOKEN.replace("\n", "").replace("\r", "").strip()

PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =============== STATES ===================

(
    DATE,
    SHIFT,
    NAME,
    START_TIME,
    END_TIME,
    TECHNIKA,
    REPRESENTATIVE,
    EQUIPMENT,
    ACTION,
) = range(9)

TECH_LIST = [
    "ЦА",
    "АЦН-10",
    "АКН",
    "АХО",
    "ППУ",
    "Цементосмеситель",
    "Автокран",
    "Звено глушения",
    "Звено СКБ",
    "Тягач",
    "Седельный тягач",
    "АЗА",
    "Седельный тягач с КМУ",
    "Бортовой с КМУ",
    "Топливозаправщик",
    "Водовозка",
    "АРОК",
    "Вахтовый автобус",
    "УАЗ",
]

# =============== HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Сетевой график ТКРС\n\nВведите дату (пример: 18.02.2026)"
    )
    return DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text

    keyboard = [["I смена", "II смена", "Обе смены"]]
    await update.message.reply_text(
        "🔄 Выберите смену",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return SHIFT


async def get_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["shift"] = update.message.text
    await update.message.reply_text("📝 Введите название операции")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("⏰ Введите время НАЧАЛА (ЧЧ:ММ)")
    return START_TIME


async def get_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["start"] = update.message.text
    await update.message.reply_text("⏰ Введите время ОКОНЧАНИЯ (ЧЧ:ММ)")
    return END_TIME


async def get_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["end"] = update.message.text

    keyboard = [[t] for t in TECH_LIST]
    await update.message.reply_text(
        "🔧 Выберите технику",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return TECHNIKA


async def get_tech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tech"] = update.message.text
    await update.message.reply_text(
        "👤 Представитель заказчика (можно написать -)"
    )
    return REPRESENTATIVE


async def get_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rep"] = update.message.text
    await update.message.reply_text(
        "📦 Оборудование и материалы (можно написать -)"
    )
    return EQUIPMENT


async def get_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["equip"] = update.message.text

    keyboard = [["➕ Добавить ещё операцию"], ["✅ Завершить отчет"]]
    await update.message.reply_text(
        "✅ Операция добавлена\n\nЧто дальше?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return ACTION


async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "Добавить" in text:
        await update.message.reply_text("📝 Введите название операции")
        return NAME

    if "Завершить" in text:
        data = context.user_data

        report = f"""
📊 ОТЧЕТ ТКРС

📅 Дата: {data.get('date')}
🔄 Смена: {data.get('shift')}
📝 Операция: {data.get('name')}
⏰ Начало: {data.get('start')}
⏰ Окончание: {data.get('end')}
🔧 Техника: {data.get('tech')}
👤 Представитель: {data.get('rep')}
📦 Оборудование: {data.get('equip')}
"""
        await update.message.reply_text(report)
        return ConversationHandler.END

    return ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено")
    return ConversationHandler.END


# =============== MAIN =================

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            SHIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shift)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_start)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_end)],
            TECHNIKA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tech)],
            REPRESENTATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rep)],
            EQUIPMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_equipment)],
            ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, action_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot started...")
    application.run_polling()


if __name__ == "__main__":
    main()
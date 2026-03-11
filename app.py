import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = TOKEN.replace("\n", "").replace("\r", "").strip()

logging.basicConfig(level=logging.INFO)

(
    BRIGADE,
    WELL,
    FIELD,
    SHIFT,
    NAME,
    START,
    END,
    TECH,
    ACTION,
) = range(9)

TECH_LIST = [
    "ЦА","АЦН-10","АКН","АХО","ППУ","Цементосмеситель",
    "Автокран","Звено глушения","Звено СКБ","Тягач",
    "Седельный тягач","АЗА","Седельный тягач с КМУ",
    "Бортовой с КМУ","Топливозаправщик","Водовозка",
    "АРОК","Вахтовый автобус","УАЗ"
]

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["▶ Начать заполнение"]],
    resize_keyboard=True
)

ACTION_KEYBOARD = ReplyKeyboardMarkup(
    [["➕ Добавить операцию"], ["✅ Завершить отчёт"]],
    resize_keyboard=True
)

SHIFT_KEYBOARD = ReplyKeyboardMarkup(
    [["I смена", "II смена"]],
    resize_keyboard=True
)

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Отчёт ТКРС\n\nНажмите начать.",
        reply_markup=MAIN_KEYBOARD
    )
    return BRIGADE


# ================== БРИГАДА ==================

async def brigade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Начать" in update.message.text:
        await update.message.reply_text("Введите номер бригады ТКРС:")
        return BRIGADE

    context.user_data["brigade"] = update.message.text
    await update.message.reply_text("Введите номер скважины:")
    return WELL


# ================== СКВАЖИНА ==================

async def well(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["well"] = update.message.text
    await update.message.reply_text("Введите месторождение:")
    return FIELD


# ================== МЕСТОРОЖДЕНИЕ ==================

async def field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["field"] = update.message.text
    context.user_data["operations"] = []
    await update.message.reply_text(
        "Выберите смену:",
        reply_markup=SHIFT_KEYBOARD
    )
    return SHIFT


# ================== СМЕНА ==================

async def shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_shift"] = update.message.text
    await update.message.reply_text("Введите название операции:")
    return NAME


# ================== НАЗВАНИЕ ==================

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_name"] = update.message.text
    await update.message.reply_text("Введите время начала (ЧЧ:ММ):")
    return START


# ================== НАЧАЛО ==================

async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_start"] = update.message.text
    await update.message.reply_text("Введите время окончания (ЧЧ:ММ):")
    return END


# ================== ОКОНЧАНИЕ ==================

async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end = update.message.text
    start = context.user_data["current_start"]

    # автоопределение смены
    try:
        start_time_obj = datetime.strptime(start, "%H:%M").time()
        if start_time_obj >= datetime.strptime("08:00", "%H:%M").time() and start_time_obj < datetime.strptime("20:00", "%H:%M").time():
            auto_shift = "I смена"
        else:
            auto_shift = "II смена"
    except:
        auto_shift = context.user_data["current_shift"]

    operation = {
        "shift": auto_shift,
        "name": context.user_data["current_name"],
        "start": start,
        "end": end,
    }

    context.user_data["operations"].append(operation)

    await update.message.reply_text(
        f"✅ Операция добавлена ({auto_shift})",
        reply_markup=ACTION_KEYBOARD
    )
    return ACTION


# ================== ДЕЙСТВИЕ ==================

async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "Добавить" in text:
        await update.message.reply_text(
            "Выберите смену:",
            reply_markup=SHIFT_KEYBOARD
        )
        return SHIFT

    if "Завершить" in text:
        ops = context.user_data["operations"]

        report = f"""
📊 ОТЧЁТ ТКРС

Бригада: {context.user_data['brigade']}
Скважина: {context.user_data['well']}
Месторождение: {context.user_data['field']}

--------------------------------------------------
"""

        report += "№ | Смена | Начало | Конец | Операция\n"
        report += "--------------------------------------------------\n"

        for i, op in enumerate(ops, 1):
            report += f"{i} | {op['shift']} | {op['start']} | {op['end']} | {op['name']}\n"

        await update.message.reply_text(report)
        return ConversationHandler.END

    return ACTION


# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            BRIGADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, brigade)],
            WELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, well)],
            FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, field)],
            SHIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, shift)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            START: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
            ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, action)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
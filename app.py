import os
import json
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"


# =======================
# ХРАНЕНИЕ
# =======================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"reports": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_number(data, brigade):
    nums = [r["number"] for r in data["reports"] if r["brigade"] == brigade]
    return max(nums) + 1 if nums else 1


# =======================
# TELEGRAM
# =======================

app = Application.builder().token(BOT_TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый отчёт", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =======================
# СОЗДАНИЕ ОТЧЁТА
# =======================

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    data = load_data()

    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта (ДД.ММ.ГГГГ):")
        context.user_data["state"] = "date"

    elif state == "date":
        context.user_data["date"] = update.message.text
        await update.message.reply_text("Введите скважину / месторождение:")
        context.user_data["state"] = "well"

    elif state == "well":
        brigade = context.user_data["brigade"]
        date = context.user_data["date"]
        well = update.message.text

        number = next_number(data, brigade)
        report_id = len(data["reports"]) + 1

        data["reports"].append({
            "id": report_id,
            "brigade": brigade,
            "number": number,
            "date": date,
            "well": well,
            "operations": []
        })

        save_data(data)
        context.user_data.clear()

        keyboard = [[InlineKeyboardButton("📂 Открыть отчёт", callback_data=f"open_{report_id}")]]
        await update.message.reply_text(
            f"✅ Отчёт №{number} создан",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= ДОБАВЛЕНИЕ ОПЕРАЦИИ =================

    elif state == "op_date":
        context.user_data["op_date"] = update.message.text
        await update.message.reply_text("Время начала (ЧЧ:ММ):")
        context.user_data["state"] = "op_start"

    elif state == "op_start":
        context.user_data["op_start"] = update.message.text
        await update.message.reply_text("Время окончания (ЧЧ:ММ):")
        context.user_data["state"] = "op_end"

    elif state == "op_end":
        context.user_data["op_end"] = update.message.text
        await update.message.reply_text("Название операции:")
        context.user_data["state"] = "op_name"

    elif state == "op_name":
        context.user_data["op_name"] = update.message.text
        await update.message.reply_text("Заявка №:")
        context.user_data["state"] = "op_req"

    elif state == "op_req":
        context.user_data["op_req"] = update.message.text
        await update.message.reply_text("Техника:")
        context.user_data["state"] = "op_eq"

    elif state == "op_eq":
        context.user_data["op_eq"] = update.message.text
        await update.message.reply_text("Представитель:")
        context.user_data["state"] = "op_rep"

    elif state == "op_rep":
        context.user_data["op_rep"] = update.message.text
        await update.message.reply_text("Материалы:")
        context.user_data["state"] = "op_mat"

    elif state == "op_mat":
        report_id = context.user_data["report_id"]

        for r in data["reports"]:
            if r["id"] == report_id:
                r["operations"].append({
                    "date": context.user_data["op_date"],
                    "start": context.user_data["op_start"],
                    "end": context.user_data["op_end"],
                    "name": context.user_data["op_name"],
                    "request": context.user_data["op_req"],
                    "equipment": context.user_data["op_eq"],
                    "rep": context.user_data["op_rep"],
                    "materials": update.message.text
                })

        save_data(data)
        context.user_data.clear()
        await show_report(update.message, report_id)


# =======================
# ПОКАЗ ОТЧЁТА
# =======================

async def show_report(message, report_id):
    data = load_data()
    report = next(r for r in data["reports"] if r["id"] == report_id)

    text = f"""📑 Отчёт №{report['number']}

📌 Бригада: {report['brigade']}
📍 Объект: {report['well']}
📅 Дата: {report['date']}

──────────────
"""

    for op in report["operations"]:
        text += f"""🔹 {op['date']} {op['start']}–{op['end']} | {op['name']}
   📄 №{op['request']}
   🚜 {op['equipment']}
   👷 {op['rep']}
   📦 {op['materials']}

"""

    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("🔄 Новый отчёт", callback_data="new")]
    ]

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def open_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    report_id = int(q.data.split("_")[1])
    await show_report(q.message, report_id)


async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    report_id = int(q.data.split("_")[1])
    context.user_data["report_id"] = report_id
    context.user_data["state"] = "op_date"
    await q.edit_message_text("Введите дату операции (ДД.ММ.ГГГГ):")


# =======================
# HANDLERS
# =======================

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
app.add_handler(CallbackQueryHandler(open_report, pattern="open_"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="add_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


if __name__ == "__main__":
    app.run_polling()
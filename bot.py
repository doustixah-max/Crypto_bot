import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀 ربات در حالت تست است.\nدکمه زیر را بزنید (فعلاً به دکمه‌ها کاری نداشته باشید):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "ریست 🔄":
        await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("دکمه زده شد! (منطق اصلی هنوز اضافه نشده)")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

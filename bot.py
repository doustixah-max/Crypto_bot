import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("تست موفق بود ✅")]]
    await update.message.reply_text("سلام! ربات با موفقیت به تلگرام متصل شد.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

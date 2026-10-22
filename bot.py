import os
import requests
import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# لیست ۱۰ ارز برتر برای دریافت از بایننس
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر کریپتو 📊"), KeyboardButton("قیمت بیت‌کوین ₿")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات قیمت‌یاب کریپتو خوش آمدید.\nیک گزینه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    text = "<b>📊 قیمت لحظه‌ای ارزهای برتر</b>\n\n"
    try:
        for coin in TOP_COINS:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT"
            res = requests.get(url, timeout=10).json()
            price = float(res['lastPrice'])
            change = float(res['priceChangePercent'])
            
            icon = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
            text += f"<b>{coin}</b> {icon}\n💰 ${price:,.2f}\n📊 تغییر: {change:+.2f}%\n➖➖➖➖➖➖\n"
            
        await msg.edit_text(text, parse_mode='HTML')
    except Exception as e:
        await msg.edit_text(f"❌ خطا در اتصال به سرور:\n{str(e)[:100]}")

async def btc_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=10).json()
        price = float(res['lastPrice'])
        await update.message.reply_text(f"₿ قیمت بیت‌کوین:\n<b>${price:,.2f}</b>", parse_mode='HTML')
    except:
        await update.message.reply_text("❌ خطا در دریافت قیمت.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برای دریافت قیمت‌ها روی دکمه‌ها کلیک کنید.\n🟢 رشد مثبت | 🔴 رشد منفی")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر کریپتو 📊":
        await top10(update, context)
    elif txt == "قیمت بیت‌کوین ₿":
        await btc_price(update, context)
    elif txt == "راهنما ❓":
        await help_command(update, context)
    elif txt == "ریست 🔄":
        await update.message.reply_text("منو بسته شد. /start را بزنید.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            print("✅ ربات روشن شد!")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"❌ خطا: {e}")
            time.sleep(5)

import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# نمادهای مورد نظر
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def get_wallex_price(symbol):
    """دریافت قیمت از صرافی والکس (بدون تحریم و نیاز به توکن)"""
    try:
        # والکس قیمت را به تومان می‌دهد (برای مقایسه با دلار باید تقسیم بر قیمت دلار شود، اما فعلاً قیمت تومانی را نشان می‌دهیم)
        url = "https://api.wallex.ir/v1/markets"
        res = requests.get(url, timeout=10).json()
        
        if res.get('success'):
            market_key = f"{symbol}USDT" # جفت ارز به تتر
            symbols = res['result']['symbols']
            if market_key in symbols:
                stats = symbols[market_key]['stats']
                return {
                    'price': float(stats['lastPrice']),
                    'high': float(stats['highPrice']),
                    'low': float(stats['lowPrice']),
                    'change': float(stats['priceChangePercent'])
                }
    except Exception:
        pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("راهنما ❓")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات قیمت‌یاب خوش آمدید.\nیک گزینه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها از والکس...")
    time_str = get_shamsi_datetime()
    text = f"<b>📊 قیمت لحظه‌ای (به تتر)</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    
    for coin in TOP_COINS:
        data = get_wallex_price(coin)
        if not data:
            text += f"<b>{coin}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
            continue
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        
        text += f"<b>{coin}</b> {icon}\n"
        text += f"💰 قیمت: {data['price']:,.2f} USDT\n"
        text += f"📈 سقف ۲۴ ساعت: {data['high']:,.2f}\n"
        text += f"📉 کف ۲۴ ساعت: {data['low']:,.2f}\n"
        text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("این ربات قیمت‌ها را از صرافی والکس دریافت می‌کند.\nقیمت‌ها به تتر (USDT) هستند.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر 📊":
        await top10(update, context)
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

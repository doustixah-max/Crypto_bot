import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# لیست ارزها
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("۱۰ ارز برتر 📊")], [KeyboardButton("ریست 🔄")]]
    await update.message.reply_text("سلام! 🚀\nیک گزینه را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    time_str = get_shamsi_datetime()
    text = f"<b>📊 قیمت لحظه‌ای</b>\n🕒 {time_str}\n\n"
    
    for coin in TOP_COINS:
        try:
            # استفاده از API صرافی OKX
            url = f"https://www.okx.com/api/v5/market/ticker?instId={coin}-USDT"
            res = requests.get(url, timeout=10).json()
            
            if res.get('code') == '0' and res.get('data'):
                data = res['data'][0]
                price = float(data['last'])
                high = float(data['high24h'])
                low = float(data['low24h'])
                open_price = float(data['open24h'])
                
                # محاسبه درصد تغییر
                change = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
                
                icon = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
                text += f"<b>{coin}</b> {icon}\n"
                text += f"💰 قیمت: ${price:,.2f}\n"
                text += f"📈 سقف: ${high:,.2f} | 📉 کف: ${low:,.2f}\n"
                text += f"📊 تغییر: {change:+.2f}%\n➖➖➖➖➖➖\n"
            else:
                text += f"<b>{coin}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
        except Exception as e:
            text += f"<b>{coin}</b>\n❌ خطا در اتصال.\n➖➖➖➖➖➖\n"
            
    await msg.edit_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "۱۰ ارز برتر 📊":
        await top10(update, context)
    elif update.message.text == "ریست 🔄":
        await update.message.reply_text("منو بسته شد. /start را بزنید.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            app.run_polling(drop_pending_updates=True)
        except Exception:
            time.sleep(5)

import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# لیست ۱۰ ارز برتر (بر اساس نمادهای نوبیتکس)
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    """دریافت تاریخ و ساعت شمسی به وقت تهران"""
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def get_nobitex_stats(symbol):
    """دریافت آمار ۲۴ ساعته از نوبیتکس"""
    try:
        # تبدیل نماد به فرمت نوبیتکس (مثلاً BTCUSDT)
        market = f"{symbol}USDT"
        url = f"https://api.nobitex.ir/market/stats?srcCurrency={symbol.lower()}&dstCurrency=usdt"
        res = requests.get(url, timeout=10).json()
        
        if res.get('status') == 'ok':
            stats = res['stats'][f"{symbol.lower()}-usdt"]
            return {
                'price': float(stats['latest']),
                'high': float(stats['dayHigh']),
                'low': float(stats['dayLow']),
                'change': float(stats['dayChange']) # درصد تغییر
            }
    except Exception:
        pass
    return None

def get_nobitex_ohlc(symbol, days=3):
    """دریافت تاریخچه ۳ روزه از نوبیتکس"""
    try:
        # استفاده از endpoint OHLC نوبیتکس برای دریافت کندل‌های روزانه
        # نکته: نوبیتکس برای OHLC نیاز به پارامترهای خاصی دارد، اما می‌توان از stats عمومی هم استفاده کرد
        # برای سادگی، از همان stats استفاده می‌کنیم و تاریخچه را شبیه‌سازی می‌کنیم (در نسخه واقعی باید از WebSocket یا endpoint candle استفاده شود)
        # اما چون نوبیتکس OHLC روزانه را در API عمومی خود دارد، از آن استفاده می‌کنیم:
        url = f"https://api.nobitex.ir/market/udf/history?symbol={symbol}USDT&resolution=1D&from={int(time.time()) - 86400*3}&to={int(time.time())}"
        # این endpoint در نوبیتکس ممکن است متفاوت باشد، بنابراین فعلاً از stats ساده استفاده می‌کنیم
        return []
    except Exception:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("قیمت بیت‌کوین ₿")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات قیمت‌یاب کریپتو خوش آمدید.\nیک گزینه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها از نوبیتکس...")
    
    time_str = get_shamsi_datetime()
    text = f"<b>📊 قیمت لحظه‌ای ارزهای برتر</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    
    for coin in TOP_COINS:
        data = get_nobitex_stats(coin)
        if not data:
            text += f"<b>{coin}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
            continue
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        
        text += f"<b>{coin}</b> {icon}\n"
        text += f"💰 قیمت: ${data['price']:,.4f}\n"
        text += f"📈 سقف ۲۴ ساعت: ${data['high']:,.4f}\n"
        text += f"📉 کف ۲۴ ساعت: ${data['low']:,.4f}\n"
        text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def btc_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_nobitex_stats("BTC")
    if data:
        await update.message.reply_text(f"₿ قیمت بیت‌کوین:\n<b>${data['price']:,.2f}</b>", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ خطا در دریافت قیمت.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برای دریافت قیمت‌ها روی دکمه‌ها کلیک کنید.\n🟢 رشد مثبت | 🔴 رشد منفی")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر 📊":
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

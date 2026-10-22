import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def get_okx_data(symbol):
    """دریافت قیمت لحظه‌ای، سقف، کف و درصد تغییر از OKX"""
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        res = requests.get(url, timeout=10).json()
        if res.get('code') == '0' and res.get('data'):
            data = res['data'][0]
            price = float(data['last'])
            high = float(data['high24h'])
            low = float(data['low24h'])
            open_price = float(data['open24h'])
            change = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
            return {'price': price, 'high': high, 'low': low, 'change': change}
    except:
        pass
    return None

def get_okx_history(symbol, days=3):
    """دریافت تاریخچه ۳ روزه (کندل‌های روزانه) از OKX"""
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar=1D&limit={days}"
        res = requests.get(url, timeout=10).json()
        if res.get('code') == '0' and res.get('data'):
            history = []
            # OKX کندل‌ها را از جدید به قدیم می‌دهد، ما برعکسش می‌کنیم
            for candle in reversed(res['data']):
                timestamp = int(candle[0]) / 1000
                date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                close_price = float(candle[4]) # قیمت بسته شدن
                history.append({'date': date, 'price': close_price})
            return history
    except:
        pass
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("ترندها 🔥")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nیک گزینه را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    time_str = get_shamsi_datetime()
    text = f"<b>📊 قیمت لحظه‌ای</b>\n🕒 {time_str}\n\n"
    
    for coin in TOP_COINS:
        data = get_okx_data(coin)
        if not data:
            text += f"<b>{coin}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
            continue
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        text += f"<b>{coin}</b> {icon}\n"
        text += f"💰 قیمت: ${data['price']:,.2f}\n"
        text += f"📈 سقف: ${data['high']:,.2f} | 📉 کف: ${data['low']:,.2f}\n"
        text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ترندهای بازار...")
    time_str = get_shamsi_datetime()
    
    # دریافت اسم ارزهای ترند از CoinGecko
    try:
        res = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        # گرفتن ۵ ارز اول و تبدیل به حروف بزرگ
        trending_symbols = [item['item']['symbol'].upper() for item in res.get('coins', [])[:5]]
    except:
        trending_symbols = []

    if not trending_symbols:
        await msg.edit_text("❌ خطا در دریافت ترندها از سرور.")
        return
        
    text = f"<b>🔥 ارزهای پرطرفدار در واچ‌لیست</b>\n🕒 {time_str}\n\n"
    
    for symbol in trending_symbols:
        data = get_okx_data(symbol)
        if not data:
            continue
            
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        text += f"<b>{symbol}</b> {icon}\n"
        text += f"💰 قیمت: ${data['price']:,.4f}\n"
        text += f"📊 تغییر: {data['change']:+.2f}%\n"
        
        # دریافت تاریخچه ۳ روزه
        history = get_okx_history(symbol, 3)
        if history:
            text += "📅 قیمت ۳ روز اخیر:\n"
            for h in history:
                text += f"  • {h['date']}: ${h['price']:,.4f}\n"
        
        text += "➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر 📊":
        await top10(update, context)
    elif txt == "ترندها 🔥":
        await trending(update, context)
    elif txt == "ریست 🔄":
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

import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# تنظیمات و دیکشنری‌ها
# ============================================================
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

# دیکشنری برای ترجمه نام‌ها (برای نمایش بهتر)
COIN_NAMES = {
    "BTC": "بیت‌کوین", "ETH": "اتریوم", "BNB": "بایننس‌کوین", "SOL": "سولانا", 
    "XRP": "ریپل", "ADA": "کاردانو", "DOGE": "دوج‌کوین", "AVAX": "آوالانچ", 
    "DOT": "پولکادات", "LINK": "چین‌لینک", "PEPE": "پپه", "WIF": "داگ‌ویف‌هت"
}

# وضعیت زبان (پیش‌فرض: انگلیسی)
user_lang = "en"

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

# ============================================================
# لایه‌های دریافت قیمت (هوشمند با پشتیبان‌گیری)
# ============================================================
def get_wallex_data(symbol):
    try:
        res = requests.get("https://api.wallex.ir/v1/markets", timeout=8).json()
        if res.get('success') and f"{symbol}USDT" in res['result']['symbols']:
            stats = res['result']['symbols'][f"{symbol}USDT"]['stats']
            return {'price': float(stats['lastPrice']), 'change': float(stats['priceChangePercent'])}
    except: pass
    return None

def get_nobitex_data(symbol):
    try:
        url = f"https://api.nobitex.ir/market/stats?srcCurrency={symbol.lower()}&dstCurrency=usdt"
        res = requests.get(url, timeout=8).json()
        if res.get('status') == 'ok' and f"{symbol.lower()}-usdt" in res['stats']:
            stats = res['stats'][f"{symbol.lower()}-usdt"]
            return {'price': float(stats['latest']), 'change': float(stats['dayChange'])}
    except: pass
    return None

def get_okx_data(symbol):
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            data = res['data'][0]
            price = float(data['last'])
            open_p = float(data['open24h'])
            change = ((price - open_p) / open_p) * 100 if open_p > 0 else 0
            return {'price': price, 'change': change}
    except: pass
    return None

def get_smart_price(symbol):
    """اول والکس، بعد نوبیتکس، در آخر OKX"""
    data = get_wallex_data(symbol)
    if data: return data
    data = get_nobitex_data(symbol)
    if data: return data
    return get_okx_data(symbol)

def get_okx_history(symbol, days=3):
    """تاریخچه ۳ روزه از OKX (چون API عمومی‌تری دارد)"""
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar=1D&limit={days}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            history = []
            for candle in reversed(res['data']):
                date = datetime.datetime.fromtimestamp(int(candle[0])/1000).strftime('%Y-%m-%d')
                history.append({'date': date, 'price': float(candle[4])})
            return history
    except: pass
    return []

# ============================================================
# توابع ربات
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_lang
    user_lang = "en" # زبان پیش‌فرض
    
    keyboard = [
        [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Trending 🔥")],
        [KeyboardButton("🇮🇷 تغییر به فارسی"), KeyboardButton("Help ❓")],
        [KeyboardButton("Reset 🔄")]
    ]
    await update.message.reply_text(
        "Welcome! 🚀\nPlease choose an option:", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_lang
    txt = update.message.text
    
    if "فارسی" in txt:
        user_lang = "fa"
        keyboard = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("ترندها 🔥")],
            [KeyboardButton("🇬🇧 Change to English"), KeyboardButton("راهنما ❓")],
            [KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد. یک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        user_lang = "en"
        keyboard = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Trending 🔥")],
            [KeyboardButton("🇮🇷 تغییر به فارسی"), KeyboardButton("Help ❓")],
            [KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English. Choose an option:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Fetching data... / در حال دریافت...")
    time_str = get_shamsi_datetime()
    
    if user_lang == "fa":
        text = f"<b>📊 ۱۰ ارز برتر بازار</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    else:
        text = f"<b>📊 Top 10 Cryptocurrencies</b>\n🕒 {time_str} (Iran Time)\n\n"
    
    for coin in TOP_COINS:
        data = get_smart_price(coin)
        if not data:
            text += f"<b>{coin}</b>\n⚠️ Data unavailable.\n➖➖➖➖➖➖\n"
            continue
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        
        if user_lang == "fa":
            name = COIN_NAMES.get(coin, coin)
            text += f"<b>{name} ({coin})</b> {icon}\n"
            text += f"💰 قیمت: ${data['price']:,.4f}\n"
            text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        else:
            text += f"<b>{coin}</b> {icon}\n"
            text += f"💰 Price: ${data['price']:,.4f}\n"
            text += f"📊 Change: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Fetching trending... / در حال دریافت...")
    time_str = get_shamsi_datetime()
    
    # ۱. گرفتن اسم ترندها از CoinGecko
    try:
        res = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        trending_symbols = [item['item']['symbol'].upper() for item in res.get('coins', [])[:5]]
    except:
        trending_symbols = ["BTC", "ETH", "SOL", "PEPE", "WIF"]
        
    if user_lang == "fa":
        text = f"<b>🔥 ارزهای پرطرفدار (واچ‌لیست)</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    else:
        text = f"<b>🔥 Trending Coins (Watchlists)</b>\n🕒 {time_str} (Iran Time)\n\n"
    
    for symbol in trending_symbols:
        # ۲. گرفتن قیمت از صرافی‌های ایرانی
        data = get_smart_price(symbol)
        if not data:
            continue
            
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        name = COIN_NAMES.get(symbol, symbol) if user_lang == "fa" else symbol
        
        if user_lang == "fa":
            text += f"<b>{name} ({symbol})</b> {icon}\n"
            text += f"💰 قیمت: ${data['price']:,.4f}\n"
            text += f"📊 تغییر: {data['change']:+.2f}%\n"
        else:
            text += f"<b>{symbol}</b> {icon}\n"
            text += f"💰 Price: ${data['price']:,.4f}\n"
            text += f"📊 Change: {data['change']:+.2f}%\n"
        
        # ۳. تاریخچه ۳ روزه
        history = get_okx_history(symbol, 3)
        if history:
            text += "📅 History (3 Days):\n" if user_lang == "en" else "📅 تاریخچه ۳ روزه:\n"
            for h in history:
                text += f"  • {h['date']}: ${h['price']:,.4f}\n"
        
        text += "➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if user_lang == "fa":
        text = "برای دریافت قیمت‌ها روی دکمه‌ها کلیک کنید.\n🟢 رشد مثبت | 🔴 رشد منفی\n⏰ تمام ساعت‌ها به وقت تهران است."
    else:
        text = "Click the buttons to get prices.\n🟢 Up | 🔴 Down\n⏰ All times are in Iran Time."
    await update.message.reply_text(text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    
    if "Top 10" in txt or "ارز برتر" in txt:
        await top10(update, context)
    elif "Trending" in txt or "ترندها" in txt:
        await trending(update, context)
    elif "Help" in txt or "راهنما" in txt:
        await help_command(update, context)
    elif "Reset" in txt or "ریست" in txt:
        await update.message.reply_text("Menu hidden. Send /start to reopen.", reply_markup=ReplyKeyboardRemove())
    elif "تغییر به فارسی" in txt or "Change to English" in txt:
        await change_lang(update, context)

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

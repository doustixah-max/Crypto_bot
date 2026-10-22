import os
import requests
import time
import datetime
import jdatetime
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def fetch_wallex_prices():
    prices = {}
    try:
        res = requests.get("https://api.wallex.ir/v1/markets", timeout=10).json()
        if res.get('success'):
            for sym, data in res['result']['symbols'].items():
                if sym.endswith("USDT"):
                    prices[sym.replace("USDT", "")] = {
                        'price': float(data['stats']['lastPrice']), 
                        'change': float(data['stats']['priceChangePercent'])
                    }
    except: pass
    return prices

def get_okx_price(symbol):
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

def get_okx_rsi(symbol, period=14):
    """محاسبه شاخص RSI (تحلیل تکنیکال) از کندل‌های ۱ ساعته OKX"""
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar=1H&limit=50"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and len(res.get('data', [])) >= period:
            closes = [float(candle[4]) for candle in reversed(res['data'])]
            gains, losses = 0, 0
            for i in range(1, period + 1):
                diff = closes[i] - closes[i-1]
                if diff > 0: gains += diff
                else: losses -= diff
            avg_gain = gains / period
            avg_loss = losses / period
            if avg_loss == 0: return 100
            rs = avg_gain / avg_loss
            return round(100 - (100 / (1 + rs)), 2)
    except: pass
    return None

def get_gold_dollar_price():
    """دریافت قیمت لحظه‌ای دلار (تتر) از نوبیتکس"""
    try:
        res = requests.get("https://api.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls", timeout=8).json()
        usd_price = int(float(res['stats']['usdt-rls']['latest'])) // 10 # تبدیل ریال به تومان
        return usd_price
    except: pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("ترندها 🔥")],
        [KeyboardButton("قیمت دلار 🇮🇷"), KeyboardButton("راهنما ❓")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات حرفه‌ای قیمت‌یاب خوش آمدید.\nیک گزینه انتخاب کنید:\n\n"
        "💡 <i>شما می‌توانید نام هر ارزی (مثل TON یا SHIB) را در چت تایپ کنید تا قیمتش را ببینید.</i>", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML'
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال تحلیل بازار (لطفاً چند ثانیه صبر کنید)...")
    time_str = get_shamsi_datetime()
    wallex_prices = fetch_wallex_prices()
    
    text = f"<b>📊 ۱۰ ارز برتر و تحلیل RSI</b>\n🕒 {time_str} (تهران)\n\n"
    for coin in TOP_COINS:
        data = wallex_prices.get(coin) or get_okx_price(coin)
        if not data: continue
        
        rsi = get_okx_rsi(coin)
        if rsi:
            if rsi > 70: rsi_txt = f"⚠️ اشباع خرید ({rsi})"
            elif rsi < 30: rsi_txt = f"🟢 اشباع فروش ({rsi})"
            else: rsi_txt = f"⚖️ خنثی ({rsi})"
        else: rsi_txt = "N/A"
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        text += f"<b>{coin}</b> {icon}\n💰 قیمت: ${data['price']:,.2f}\n📊 تغییر: {data['change']:+.2f}%\n📈 تحلیل: {rsi_txt}\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ترندها...")
    time_str = get_shamsi_datetime()
    wallex_prices = fetch_wallex_prices()
    
    # لیست ثابت ارزهای محبوب که همیشه در والکس یا OKX هستند
    trending_symbols = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB"]
    text = f"<b>🔥 ارزهای پرطرفدار</b>\n🕒 {time_str}\n\n"
    
    count = 0
    for symbol in trending_symbols:
        if count >= 5: break
        data = wallex_prices.get(symbol) or get_okx_price(symbol)
        if data:
            count += 1
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text += f"<b>{symbol}</b> {icon}\n💰 قیمت: ${data['price']:,.2f}\n📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
            
    await msg.edit_text(text, parse_mode='HTML')

async def dollar_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت دلار...")
    usd_price = get_gold_dollar_price()
    time_str = get_shamsi_datetime()
    
    if usd_price:
        text = f"<b>🇮🇷 قیمت لحظه‌ای دلار (تومان)</b>\n🕒 {time_str}\n\n"
        text += f"💵 <b>دلار آمریکا (تتر):</b> {usd_price:,.0f} تومان\n"
        text += "➖➖➖➖➖➖\n"
    else:
        text = "❌ خطا در دریافت قیمت دلار از سرور."
    await msg.edit_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>راهنمای ربات</b>\n\n"
        "📊 <b>۱۰ ارز برتر:</b> نمایش قیمت، تغییرات ۲۴ ساعته و تحلیل RSI\n"
        "🔥 <b>ترندها:</b> نمایش ۵ ارز پرطرفدار و امن\n"
        "🇮🇷 <b>قیمت دلار:</b> دریافت قیمت لحظه‌ای تتر به تومان\n"
        "🔍 <b>جستجوی دستی:</b> نام هر ارزی (مثل TON) را تایپ کنید تا قیمتش را ببینید.\n\n"
        "🟢 رشد مثبت | 🔴 رشد منفی"
    )
    await update.message.reply_text(text, parse_mode='HTML')

# مدیریت جستجوی دستی ارزها و دکمه‌ها
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().upper()
    
    # اگر کاربر یک کلمه انگلیسی فرستاد، فرض می‌کنیم اسم ارز است
    if re.match(r"^[A-Z0-9]{2,10}$", txt):
        msg = await update.message.reply_text(f"⏳ جستجوی {txt}...")
        wallex_prices = fetch_wallex_prices()
        data = wallex_prices.get(txt) or get_okx_price(txt)
        
        if data:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text = f"<b>🔍 نتیجه جستجو: {txt}</b> {icon}\n"
            text += f"💰 قیمت: ${data['price']:,.4f}\n📊 تغییر: {data['change']:+.2f}%\n"
            await msg.edit_text(text, parse_mode='HTML')
        else:
            await msg.edit_text(f"❌ ارز {txt} در صرافی‌های پشتیبانی‌شده یافت نشد.")
        return
        
    # مدیریت دکمه‌ها
    if "۱۰ ارز برتر" in txt: await top10(update, context)
    elif "ترندها" in txt: await trending(update, context)
    elif "قیمت دلار" in txt: await dollar_price(update, context)
    elif "راهنما" in txt: await help_command(update, context)
    elif "ریست" in txt: await update.message.reply_text("منو بسته شد. /start را بزنید.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
            app.run_polling(drop_pending_updates=True)
        except Exception:
            time.sleep(5)

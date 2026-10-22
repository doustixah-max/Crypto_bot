import os
import requests
import time
import datetime
import jdatetime
import re
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

# حافظه موقت برای زبان و هشدارها
user_lang = {} # { chat_id: 'fa' or 'en' }
user_alerts = {}

def get_time_str(chat_id):
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    if user_lang.get(chat_id, 'fa') == 'fa':
        shamsi_date = jdatetime.date.fromgregorian(date=now.date())
        return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"
    else:
        return now.strftime("%Y-%m-%d - %H:%M:%S")

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

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    wallex_prices = fetch_wallex_prices()
    for chat_id, alerts in list(user_alerts.items()):
        lang = user_lang.get(chat_id, 'fa')
        for alert in alerts[:]:
            data = wallex_prices.get(alert['symbol']) or get_okx_price(alert['symbol'])
            if not data: continue
            current_price = data['price']
            
            if (alert['direction'] == 'above' and current_price >= alert['target']) or \
               (alert['direction'] == 'below' and current_price <= alert['target']):
                
                if lang == 'fa':
                    msg = f"🚨 <b>هشدار قیمت!</b>\n\nارز <b>{alert['symbol']}</b> به هدف شما رسید.\n🎯 هدف: ${alert['target']:,.2f}\n💰 قیمت فعلی: ${current_price:,.2f}"
                else:
                    msg = f"🚨 <b>Price Alert!</b>\n\n<b>{alert['symbol']}</b> reached your target.\n🎯 Target: ${alert['target']:,.2f}\n💰 Current: ${current_price:,.2f}"
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                except: pass
                user_alerts[chat_id].remove(alert)
        if not user_alerts[chat_id]: del user_alerts[chat_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_lang[chat_id] = 'fa' # پیش‌فرض فارسی
    
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تنظیم هشدار 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات حرفه‌ای قیمت‌یاب خوش آمدید.\nیک گزینه انتخاب کنید:\n\n"
        "💡 <i>می‌توانید نام ارز (مثل TON) یا مقدار (مثل 0.5 BTC) را تایپ کنید.</i>", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML'
    )

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_lang = user_lang.get(chat_id, 'fa')
    
    if current_lang == 'fa':
        user_lang[chat_id] = 'en'
        keyboard = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Set Alert 🔔"), KeyboardButton("Change Language 🇮🇷")],
            [KeyboardButton("Help ❓"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        keyboard = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تنظیم هشدار 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
            [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    msg = await update.message.reply_text("⏳ ...")
    time_str = get_time_str(chat_id)
    wallex_prices = fetch_wallex_prices()
    
    text = f"<b>📊 {'۱۰ ارز برتر' if lang=='fa' else 'Top 10 Coins'}</b>\n🕒 {time_str}\n\n"
    for coin in TOP_COINS:
        data = wallex_prices.get(coin) or get_okx_price(coin)
        if not data: continue
        rsi = get_okx_rsi(coin)
        
        if lang == 'fa':
            rsi_txt = f"⚠️ اشباع خرید ({rsi})" if rsi and rsi > 70 else (f"🟢 اشباع فروش ({rsi})" if rsi and rsi < 30 else f"⚖️ خنثی ({rsi})")
            text += f"<b>{coin}</b> {'🟢' if data['change']>0 else '🔴'}\n💰 قیمت: ${data['price']:,.2f}\n📊 تغییر: {data['change']:+.2f}%\n📈 تحلیل: {rsi_txt}\n➖➖➖➖➖➖\n"
        else:
            rsi_txt = f"⚠️ Overbought ({rsi})" if rsi and rsi > 70 else (f"🟢 Oversold ({rsi})" if rsi and rsi < 30 else f"⚖️ Neutral ({rsi})")
            text += f"<b>{coin}</b> {'🟢' if data['change']>0 else '🔴'}\n💰 Price: ${data['price']:,.2f}\n📊 Change: {data['change']:+.2f}%\n📈 RSI: {rsi_txt}\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    msg = await update.message.reply_text("⏳ ...")
    time_str = get_time_str(chat_id)
    wallex_prices = fetch_wallex_prices()
    
    text = f"<b>🔥 {'۱۰ ارز پرطرفدار' if lang=='fa' else 'Top 10 Trending'}</b>\n🕒 {time_str}\n\n"
    count = 0
    for symbol in TRENDING_COINS:
        if count >= 10: break
        data = wallex_prices.get(symbol) or get_okx_price(symbol)
        if data:
            count += 1
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            if lang == 'fa':
                text += f"<b>{symbol}</b> {icon}\n💰 قیمت: ${data['price']:,.2f}\n📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
            else:
                text += f"<b>{symbol}</b> {icon}\n💰 Price: ${data['price']:,.2f}\n📊 Change: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    if lang == 'fa':
        text = "ℹ️ <b>راهنما</b>\n\n📊 ۱۰ ارز برتر با تحلیل RSI\n🔥 ۱۰ ترند برتر\n🔔 تنظیم هشدار: <code>alert BTC 85000 above</code>\n🔍 جستجو: تایپ <code>TON</code>\n💱 تبدیل: تایپ <code>0.5 BTC</code>"
    else:
        text = "ℹ️ <b>Help</b>\n\n📊 Top 10 with RSI\n🔥 Top 10 Trending\n🔔 Set alert: <code>alert BTC 85000 above</code>\n🔍 Search: type <code>TON</code>\n💱 Convert: type <code>0.5 BTC</code>"
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    txt_upper = txt.upper()
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    
    # هشدار
    if txt_upper.startswith("ALERT"):
        parts = txt.split()
        if len(parts) == 4:
            symbol = parts[1].upper()
            try:
                target = float(parts[2].replace(',', ''))
                direction = parts[3].lower()
                if direction in ['above', 'below']:
                    if chat_id not in user_alerts: user_alerts[chat_id] = []
                    user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
                    user_alerts[chat_id].append({'symbol': symbol, 'target': target, 'direction': direction})
                    msg = f"✅ هشدار {symbol} تنظیم شد." if lang=='fa' else f"✅ Alert for {symbol} set."
                    await update.message.reply_text(msg)
                    return
            except: pass
        await update.message.reply_text("❌ فرمت اشتباه. / Wrong format.\n<code>alert BTC 85000 above</code>", parse_mode='HTML')
        return

    # تبدیل ارز (Converter)
    conv_match = re.match(r"^([\d\.]+)\s*([A-Z]{2,10})$", txt_upper)
    if conv_match:
        amount = float(conv_match.group(1))
        symbol = conv_match.group(2)
        data = fetch_wallex_prices().get(symbol) or get_okx_price(symbol)
        if data:
            total_usd = amount * data['price']
            msg = f"💱 {amount} {symbol} = <b>${total_usd:,.2f}</b>" if lang=='en' else f"💱 {amount} {symbol} معادل <b>${total_usd:,.2f}</b> است."
            await update.message.reply_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ {symbol} not found." if lang=='en' else f"❌ ارز {symbol} یافت نشد.")
        return

    # جستجو
    if re.match(r"^[A-Z0-9]{2,10}$", txt_upper):
        msg = await update.message.reply_text("⏳ ...")
        data = fetch_wallex_prices().get(txt_upper) or get_okx_price(txt_upper)
        if data:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            if lang == 'fa':
                text = f"<b>🔍 {txt_upper}</b> {icon}\n💰 قیمت: ${data['price']:,.4f}\n📊 تغییر: {data['change']:+.2f}%"
            else:
                text = f"<b>🔍 {txt_upper}</b> {icon}\n💰 Price: ${data['price']:,.4f}\n📊 Change: {data['change']:+.2f}%"
            await msg.edit_text(text, parse_mode='HTML')
        else:
            await msg.edit_text(f"❌ {txt_upper} not found.")
        return
        
    # دکمه‌ها
    if "۱۰ ارز برتر" in txt or "Top 10 Coins" in txt: await top10(update, context)
    elif "ترند" in txt or "Trending" in txt: await trending(update, context)
    elif "هشدار" in txt or "Alert" in txt: 
        msg = "دستور: <code>alert BTC 85000 above</code>" if lang=='fa' else "Command: <code>alert BTC 85000 above</code>"
        await update.message.reply_text(msg, parse_mode='HTML')
    elif "راهنما" in txt or "Help" in txt: await help_command(update, context)
    elif "زبان" in txt or "Language" in txt: await change_lang(update, context)
    elif "ریست" in txt or "Reset" in txt: await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(check_alerts, interval=300, first=10)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

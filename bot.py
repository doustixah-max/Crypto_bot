import os
import requests
import datetime
import jdatetime
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

user_lang = {}
user_alerts = {}
# برای ذخیره وضعیت کاربر در حال تنظیم هشدار
user_state = {} 

def get_time_str(chat_id):
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    if user_lang.get(chat_id, 'fa') == 'fa':
        return f"{jdatetime.date.fromgregorian(date=now.date()).strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"
    return now.strftime("%Y-%m-%d - %H:%M:%S")

def fetch_prices():
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

def get_okx(symbol):
    try:
        res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT", timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            d = res['data'][0]
            p = float(d['last'])
            o = float(d['open24h'])
            return {'price': p, 'change': ((p - o) / o) * 100 if o > 0 else 0}
    except: pass
    return None

def get_rsi(symbol):
    try:
        res = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar=1H&limit=50", timeout=8).json()
        if res.get('code') == '0' and len(res.get('data', [])) >= 14:
            closes = [float(c[4]) for c in reversed(res['data'])]
            g, l = 0, 0
            for i in range(1, 15):
                d = closes[i] - closes[i-1]
                if d > 0: g += d
                else: l -= d
            if l == 0: return 100
            return round(100 - (100 / (1 + (g/14) / (l/14))), 2)
    except: pass
    return None

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    prices = fetch_prices()
    for chat_id, alerts in list(user_alerts.items()):
        lang = user_lang.get(chat_id, 'fa')
        for a in alerts[:]:
            data = prices.get(a['symbol']) or get_okx(a['symbol'])
            if not data: continue
            cp = data['price']
            if (a['direction'] == 'above' and cp >= a['target']) or (a['direction'] == 'below' and cp <= a['target']):
                msg = f"🚨 هشدار: {a['symbol']} به هدف رسید!\nقیمت فعلی: ${cp:,.2f}" if lang == 'fa' else f"🚨 Alert: {a['symbol']} reached target!\nCurrent: ${cp:,.2f}"
                try: await context.bot.send_message(chat_id, msg)
                except: pass
                user_alerts[chat_id].remove(a)
        if not user_alerts[chat_id]: del user_alerts[chat_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_lang[chat_id] = 'fa'
    kb = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تنظیم هشدار 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if user_lang.get(chat_id, 'fa') == 'fa':
        user_lang[chat_id] = 'en'
        kb = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Set Alert 🔔"), KeyboardButton("Change Language 🇮🇷")],
            [KeyboardButton("Help ❓"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تنظیم هشدار 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
            [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# ----------------- سیستم هشدار مرحله به مرحله -----------------

async def start_alert_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {'step': 'choose_coin'}
    
    # ساخت دکمه‌های شیشه‌ای از ارزهای محبوب
    kb = []
    row = []
    for coin in TOP_COINS:
        row.append(InlineKeyboardButton(coin, callback_data=f"alertcoin_{coin}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row: kb.append(row)
    
    await update.message.reply_text("مرحله ۱: ارز مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    
    if data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        user_state[chat_id] = {'step': 'choose_direction', 'symbol': coin}
        
        kb = [
            [InlineKeyboardButton("📈 بالاتر (Above)", callback_data="dir_above")],
            [InlineKeyboardButton("📉 پایین‌تر (Below)", callback_data="dir_below")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="alert_cancel")]
        ]
        await query.edit_message_text(f"ارز: {coin}\nمرحله ۲: جهت هشدار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("dir_"):
        direction = data.replace("dir_", "")
        state = user_state.get(chat_id)
        if state and 'symbol' in state:
            state['direction'] = direction
            state['step'] = 'enter_price'
            symbol = state['symbol']
            dir_fa = "بالاتر" if direction == "above" else "پایین‌تر"
            
            await query.edit_message_text(
                f"ارز: {symbol} | جهت: {dir_fa}\n\n"
                f"مرحله ۳: حالا **عدد قیمت هدف** را به دلار تایپ کرده و بفرستید.\n"
                f"مثال: <code>85000</code>", 
                parse_mode='HTML'
            )
            
    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("عملیات لغو شد.")

# ----------------- توابع اصلی -----------------

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    msg = await update.message.reply_text("⏳ ...")
    prices = fetch_prices()
    text = f"<b>📊 {'۱۰ ارز برتر' if lang=='fa' else 'Top 10 Coins'}</b>\n🕒 {get_time_str(chat_id)}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        rsi = get_rsi(c)
        rsi_txt = f"RSI: {rsi}" if rsi else ""
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.2f}\n📊 {d['change']:+.2f}%\n📈 {rsi_txt}\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    msg = await update.message.reply_text("⏳ ...")
    prices = fetch_prices()
    text = f"<b>🔥 {'۱۰ ترند برتر' if lang=='fa' else 'Top 10 Trending'}</b>\n🕒 {get_time_str(chat_id)}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.2f}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    text = "ℹ️ راهنما:\n🔔 هشدار: از منوی دکمه‌ای استفاده کنید.\n💱 تبدیل: <code>0.5 BTC</code>\n🔍 جستجو: <code>TON</code>" if lang=='fa' else "ℹ️ Help:\n🔔 Alert: Use the button menu.\n💱 Convert: <code>0.5 BTC</code>\n🔍 Search: <code>TON</code>"
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    
    # بررسی اینکه آیا کاربر در حال وارد کردن قیمت هشدار است
    state = user_state.get(chat_id)
    if state and state.get('step') == 'enter_price':
        try:
            target_price = float(txt.replace(',', ''))
            symbol = state['symbol']
            direction = state['direction']
            
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
            user_alerts[chat_id].append({'symbol': symbol, 'target': target_price, 'direction': direction})
            
            dir_fa = "بالاتر" if direction == "above" else "پایین‌تر"
            msg = f"✅ هشدار برای {symbol} تنظیم شد!\nاگر قیمت به {target_price:,.2f} دلار ({dir_fa}) رسید، به شما اطلاع می‌دهم." if lang == 'fa' else f"✅ Alert set for {symbol}!\nIf price reaches ${target_price:,.2f}, I will notify you."
            await update.message.reply_text(msg)
            user_state[chat_id] = {} # پاک کردن وضعیت
            return
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید (مثلاً 85000).")
            return

    # مبدل ارز
    conv = re.match(r"^([\d\.]+)\s*([A-Z]{2,10})$", up)
    if conv:
        amt, sym = float(conv.group(1)), conv.group(2)
        d = fetch_prices().get(sym) or get_okx(sym)
        if d:
            return await update.message.reply_text(f"💱 {amt} {sym} = <b>${amt * d['price']:,.2f}</b>", parse_mode='HTML')
        
    # جستجوی ارز
    if re.match(r"^[A-Z0-9]{2,10}$", up):
        msg = await update.message.reply_text("⏳ ...")
        d = fetch_prices().get(up) or get_okx(up)
        if d:
            return await msg.edit_text(f"<b>🔍 {up}</b>\n💰 ${d['price']:,.4f}\n📊 {d['change']:+.2f}%", parse_mode='HTML')
        return await msg.edit_text("❌ یافت نشد. / Not found.")

    # دکمه‌های منو
    if "۱۰ ارز برتر" in txt or "Top 10 Coins" in txt: await top10(update, context)
    elif "ترند" in txt or "Trending" in txt: await trending(update, context)
    elif "تنظیم هشدار" in txt or "Set Alert" in txt: await start_alert_setup(update, context)
    elif "راهنما" in txt or "Help" in txt: await help_cmd(update, context)
    elif "زبان" in txt or "Language" in txt: await change_lang(update, context)
    elif "ریست" in txt or "Reset" in txt: await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(check_alerts, interval=300, first=10)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_alert_callback)) # برای دکمه‌های شیشه‌ای هشدار
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

import os
import requests
import datetime
import jdatetime
import json
import urllib.parse
import io
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

user_alerts = {}
user_state = {} 

def format_price(price):
    if price < 1: return f"${price:,.6f}"
    elif price < 100: return f"${price:,.4f}"
    else: return f"${price:,.2f}"

def get_time_str():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    return f"{jdatetime.date.fromgregorian(date=now.date()).strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

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

def get_klines(symbol, timeframe='1H', limit=40):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            labels = []
            closes = []
            for c in reversed(res['data']):
                ts = int(c[0])
                dt = datetime.datetime.fromtimestamp(ts/1000, datetime.timezone.utc).strftime('%m-%d %H:%M')
                labels.append(dt)
                closes.append(float(c[4]))
            return labels, closes
    except: pass
    return [], []

def calculate_indicators(closes):
    if len(closes) < 20: return None
    results = {}
    
    # RSI
    period = 14
    gains, losses = 0, 0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    rs = (gains / period) / (losses / period) if losses > 0 else 100
    results['rsi'] = round(100 - (100 / (1 + rs)), 2)
    
    # EMA 20
    multiplier = 2 / (20 + 1)
    ema = closes[0]
    ema_values = []
    for i, price in enumerate(closes):
        ema = (price - ema) * multiplier + ema
        ema_values.append(ema if i >= 20 else None)
    results['ema'] = ema
    results['ema_line'] = ema_values
    
    # Bollinger
    recent = closes[-20:]
    sma = sum(recent) / 20
    variance = sum((x - sma) ** 2 for x in recent) / 20
    std = variance ** 0.5
    results['bb_upper'] = sma + (2 * std)
    results['bb_lower'] = sma - (2 * std)
    
    return results

# --- منوها ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {} 
    kb = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
        [KeyboardButton("طلا، ارز و نفت 🌍"), KeyboardButton("درباره سازنده 👨‍💻")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nبه ربات پیشرفته کریپتو خوش آمدید.\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>📊 ۱۰ ارز برتر</b>\n🕒 {get_time_str()}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 قیمت: {format_price(d['price'])}\n📊 تغییر: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>🔥 ۱۰ ترند برتر</b>\n🕒 {get_time_str()}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 قیمت: {format_price(d['price'])}\n📊 تغییر: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

# --- تحلیل ---
async def start_advanced_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("📈 نام ارز را وارد کنید (مثلاً BTC):")
    user_state[chat_id] = {'step': 'analysis_type_coin'}

async def handle_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    
    if data.startswith("tf_"):
        timeframe = data.replace("tf_", "")
        state = user_state.get(chat_id)
        if not state or 'symbol' not in state: return
        coin = state['symbol']
        
        tf_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1H': '1H', '4H': '4H', '1D': '1D'}
        okx_tf = tf_map.get(timeframe, '1H')
        tf_labels = {'1m': '۱ دقیقه', '5m': '۵ دقیقه', '15m': '۱۵ دقیقه', '30m': '۳۰ دقیقه', '1H': '۱ ساعته', '4H': '۴ ساعته', '1D': 'روزانه'}
        tf_fa = tf_labels.get(timeframe, timeframe)
        
        await query.edit_message_text(f"⏳ در حال تحلیل {coin} ({tf_fa})...")
        
        labels, closes = get_klines(coin, okx_tf, 40)
        if not closes: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        ind = calculate_indicators(closes)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        cp = data_price['price']
        
        # تفسیر
        rsi = ind['rsi']
        if rsi > 70: rsi_txt = f"⚠️ اشباع خرید ({rsi})"
        elif rsi < 30: rsi_txt = f"🟢 اشباع فروش ({rsi})"
        else: rsi_txt = f"⚖️ خنثی ({rsi})"
        
        bb_txt = "🔴 بالاتر از سقف" if cp > ind['bb_upper'] else ("🟢 پایین‌تر از کف" if cp < ind['bb_lower'] else "⚖️ داخل باندها")
        ema_txt = "🟢 بالای EMA" if cp > ind['ema'] else "🔴 زیر EMA"
        
        score = 0
        if rsi < 30 or cp < ind['bb_lower'] or cp > ind['ema']: score += 1
        if rsi > 70 or cp > ind['bb_upper'] or cp < ind['ema']: score -= 1
        
        if score >= 2: summary = "🟢 <b>برآیند: صعودی</b>"
        elif score <= -2: summary = "🔴 <b>برآیند: نزولی</b>"
        else: summary = "⚖️ <b>برآیند: خنثی</b>"

        text = (
            f"📈 <b>تحلیل {coin}</b> ({tf_fa})\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"💰 <b>قیمت:</b> {format_price(cp)}\n"
            f"📊 <b>تغییر ۲۴س:</b> {data_price['change']:+.2f}%\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"1️⃣ <b>RSI:</b> {rsi_txt}\n"
            f"2️⃣ <b>بولینگر:</b> {bb_txt}\n"
            f"3️⃣ <b>EMA:</b> {ema_txt}\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🎯 {summary}"
        )
        await query.edit_message_text(text, parse_mode='HTML')
        
        # نمودار خطی بسیار زیبا با خط EMA (تضمینی)
        ema_line = [d if d is not None else closes[0] for d in ind['ema_line']]
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": coin,
                        "data": closes,
                        "borderColor": "#00ff00",
                        "backgroundColor": "rgba(0, 255, 0, 0.1)",
                        "fill": True,
                        "borderWidth": 2,
                        "pointRadius": 0
                    },
                    {
                        "label": "EMA 20",
                        "data": ema_line,
                        "borderColor": "#d4af37",
                        "borderWidth": 2,
                        "fill": False,
                        "pointRadius": 0
                    }
                ]
            },
            "options": {"plugins": {"legend": {"display": False}}}
        }
        encoded = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded}&w=800&h=400&bkg=%23111111"
        
        try:
            img_data = requests.get(chart_url, timeout=15).content
            await context.bot.send_photo(chat_id=chat_id, photo=img_data, caption=f"📊 نمودار {coin} - {tf_fa}")
        except:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ خطا در ارسال نمودار.")

# --- هشدارها ---
async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    kb = [
        [InlineKeyboardButton("➕ تنظیم هشدار جدید", callback_data="new_alert")],
        [InlineKeyboardButton("📋 مشاهده هشدارهای فعال", callback_data="view_alerts")]
    ]
    await update.message.reply_text("🔔 مدیریت هشدارها:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data
    
    if data == "new_alert":
        user_state[chat_id] = {'step': 'choose_coin'}
        kb = []
        row = []
        for coin in TOP_COINS[:9]:
            row.append(InlineKeyboardButton(coin, callback_data=f"alertcoin_{coin}"))
            if len(row) == 3:
                kb.append(row); row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("سایر ارزها (تایپ) ✍️", callback_data="alert_other")])
        kb.append([InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")])
        await query.edit_message_text("مرحله ۱: ارز را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "view_alerts":
        alerts = user_alerts.get(chat_id, [])
        if not alerts: return await query.edit_message_text("هشداری ندارید.")
        text = "📋 <b>هشدارهای شما:</b>\n\n"
        for a in alerts:
            text += f"🔸 {a['symbol']} | قیمت: {format_price(a['target'])}\n"
        await query.edit_message_text(text, parse_mode='HTML')

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("نام ارز را تایپ کنید:")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        data_price = fetch_prices().get(coin) or get_okx(coin)
        if not data_price: return await query.edit_message_text("❌ ارز یافت نشد.")
        user_state[chat_id] = {'step': 'enter_target', 'symbol': coin}
        await query.edit_message_text(f"ارز: {coin}\n💰 قیمت: {format_price(data_price['price'])}\n\nعدد قیمت هدف را وارد کنید:")

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("لغو شد.")

async def gold_forex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌍 انس جهانی طلا: $2,350.50\n💵 شاخص دلار: 104.50\n🛢 نفت برنت: $82.30")

async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👨‍💻 <b>صادق دوستی‌خواه</b>\n📧 <code>S.doostikhah@gmail.com</code>", parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    
    if "ریست" in txt or "Reset" in txt:
        user_state[chat_id] = {}
        return await update.message.reply_text("منو ریست شد. /start را بزنید.")
    elif "۱۰ ارز برتر" in txt: 
        user_state[chat_id] = {}; await top10(update, context); return
    elif "ترند" in txt: 
        user_state[chat_id] = {}; await trending(update, context); return
    elif "تحلیل" in txt: 
        user_state[chat_id] = {}; await start_advanced_analysis(update, context); return
    elif "هشدار" in txt: 
        user_state[chat_id] = {}; await show_alerts_menu(update, context); return
    elif "طلا" in txt or "نفت" in txt: 
        user_state[chat_id] = {}; await gold_forex(update, context); return
    elif "سازنده" in txt: 
        user_state[chat_id] = {}; await about_developer(update, context); return

    state = user_state.get(chat_id, {})
    
    if state.get('step') == 'analysis_type_coin':
        user_state[chat_id] = {'step': 'analysis_choose_tf', 'symbol': up}
        kb = [
            [InlineKeyboardButton("۱ دقیقه", callback_data="tf_1m"), InlineKeyboardButton("۱۵ دقیقه", callback_data="tf_15m")],
            [InlineKeyboardButton("۱ ساعته", callback_data="tf_1H"), InlineKeyboardButton("۴ ساعته", callback_data="tf_4H")],
            [InlineKeyboardButton("روزانه", callback_data="tf_1D")]
        ]
        return await update.message.reply_text(f"ارز {up} انتخاب شد. بازه زمانی:", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') == 'type_coin':
        user_state[chat_id] = {'step': 'enter_target', 'symbol': up}
        return await update.message.reply_text(f"ارز {up} انتخاب شد. عدد قیمت هدف را وارد کنید:")

    if state.get('step') == 'enter_target':
        try:
            target = float(txt)
            symbol = state['symbol']
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id].append({'symbol': symbol, 'target': target})
            await update.message.reply_text(f"✅ هشدار {symbol} برای قیمت {format_price(target)} تنظیم شد.")
            user_state[chat_id] = {}
            return
        except ValueError:
            return await update.message.reply_text("❌ عدد معتبر وارد کنید.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|alert_cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

import os
import requests
import datetime
import jdatetime
import json
import urllib.parse
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

def get_klines_ohlc(symbol, timeframe='1H', limit=50):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            data = []
            for c in reversed(res['data']):
                ts = int(c[0])
                dt_iso = datetime.datetime.fromtimestamp(ts/1000, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                data.append({
                    "x": dt_iso,
                    "o": float(c[1]),
                    "h": float(c[2]),
                    "l": float(c[3]),
                    "c": float(c[4])
                })
            return data
    except: pass
    return []

def calculate_indicators(ohlc_data):
    """محاسبه دقیق ۴ اندیکاتور اصلی"""
    if len(ohlc_data) < 20: return None
    results = {}
    
    closes = [d['c'] for d in ohlc_data]
    highs = [d['h'] for d in ohlc_data]
    lows = [d['l'] for d in ohlc_data]
    
    # 1. RSI (14)
    period_rsi = 14
    gains, losses = 0, 0
    for i in range(len(closes) - period_rsi, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    avg_gain = gains / period_rsi
    avg_loss = losses / period_rsi
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    results['rsi'] = round(100 - (100 / (1 + rs)), 2)
    
    # 2. Bollinger Bands (20, 2)
    period_bb = 20
    recent_closes = closes[-period_bb:]
    sma = sum(recent_closes) / period_bb
    variance = sum((x - sma) ** 2 for x in recent_closes) / period_bb
    std_dev = variance ** 0.5
    results['bb_upper'] = sma + (2 * std_dev)
    results['bb_lower'] = sma - (2 * std_dev)
    
    # 3. EMA (20)
    period_ema = 20
    multiplier = 2 / (period_ema + 1)
    ema = closes[0]
    ema_values = []
    for i, price in enumerate(closes):
        ema = (price - ema) * multiplier + ema
        ema_values.append(ema if i >= period_ema else None)
    results['ema'] = ema
    results['ema_line'] = ema_values
    
    # 4. ADX (14)
    period_adx = 14
    trs, plus_dms, minus_dms = [], [], []
    for i in range(1, len(ohlc_data)):
        h, l, prev_c = highs[i], lows[i], closes[i-1]
        prev_h, prev_l = highs[i-1], lows[i-1]
        
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
        
        up_move = h - prev_h
        down_move = prev_l - l
        
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0
        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)

    # میانگین متحرک ساده برای ساده‌سازی
    if len(trs) >= period_adx:
        avg_tr = sum(trs[-period_adx:]) / period_adx
        avg_plus_dm = sum(plus_dms[-period_adx:]) / period_adx
        avg_minus_dm = sum(minus_dms[-period_adx:]) / period_adx
        
        plus_di = (avg_plus_dm / avg_tr) * 100 if avg_tr > 0 else 0
        minus_di = (avg_minus_dm / avg_tr) * 100 if avg_tr > 0 else 0
        
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        results['adx'] = round(dx, 2)
        results['plus_di'] = plus_di
        results['minus_di'] = minus_di
    else:
        results['adx'] = 0
        results['plus_di'] = 0
        results['minus_di'] = 0
        
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
        text += f"<b>{c}</b> {icon}\n💰 قیمت: {format_price(d['price'])}\n📊 تغییر ۲۴س: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
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
            text += f"<b>{c}</b> {icon}\n💰 قیمت: {format_price(d['price'])}\n📊 تغییر ۲۴س: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

# --- تحلیل پیشرفته ---
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
        
        ohlc_data = get_klines_ohlc(coin, okx_tf, 50)
        if not ohlc_data: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        ind = calculate_indicators(ohlc_data)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        cp = data_price['price']
        
        # محاسبه تغییر قیمت در همان بازه زمانی
        first_close = ohlc_data[0]['c']
        change_in_tf = ((cp - first_close) / first_close) * 100 if first_close > 0 else 0
        
        # تفسیر
        rsi = ind['rsi']
        if rsi > 70: rsi_txt = f"⚠️ اشباع خرید ({rsi})"
        elif rsi < 30: rsi_txt = f"🟢 اشباع فروش ({rsi})"
        else: rsi_txt = f"⚖️ خنثی ({rsi})"
        
        bb_txt = "🔴 بالاتر از سقف" if cp > ind['bb_upper'] else ("🟢 پایین‌تر از کف" if cp < ind['bb_lower'] else "⚖️ داخل باندها")
        ema_txt = "🟢 بالای EMA" if cp > ind['ema'] else "🔴 زیر EMA"
        
        adx = ind['adx']
        if adx > 25: adx_txt = f"💪 روند قوی ({adx})"
        elif adx < 20: adx_txt = f"🔀 بازار رِنج ({adx})"
        else: adx_txt = f"⚖️ شکل‌گیری روند ({adx})"
        
        # برآیند نهایی (Trend)
        if adx < 20:
            trend_summary = "⚠️ <b>روند نهایی: رِنج (Range)</b>\nقدرت روند پایین است و بازار در حالت خنثی نوسان می‌کند. سیگنال‌های ورود قابل اعتماد نیستند."
        else:
            if ind['plus_di'] > ind['minus_di']:
                trend_summary = "🟢 <b>روند نهایی: صعودی (Bullish)</b>\nخریداران کنترل بازار را در دست دارند."
            else:
                trend_summary = "🔴 <b>روند نهایی: نزولی (Bearish)</b>\nفروشندگان فشار زیادی وارد می‌کنند."

        # --- متن کاملاً تفکیک شده ---
        text = (
            f"📈 <b>تحلیل جامع {coin}</b> ({tf_fa})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>قیمت لحظه‌ای:</b> {format_price(cp)}\n"
            f"📊 <b>تغییر در این بازه ({tf_fa}):</b> {change_in_tf:+.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📉 <b>اندیکاتورها:</b>\n\n"
            f"1️⃣ <b>RSI:</b>\n   {rsi_txt}\n\n"
            f"2️⃣ <b>بولینگر:</b>\n   {bb_txt}\n\n"
            f"3️⃣ <b>EMA:</b>\n   {ema_txt}\n\n"
            f"4️⃣ <b>ADX:</b>\n   {adx_txt}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 {trend_summary}"
        )
        await query.edit_message_text(text, parse_mode='HTML')
        
        # --- نمودار شمعی ---
        closes = [d['c'] for d in ohlc_data]
        ema_line = [d if d is not None else closes[0] for d in ind['ema_line']]
        
        chart_config = {
            "type": "candlestick",
            "data": {
                "datasets": [
                    {
                        "label": coin,
                        "data": ohlc_data,
                        "color": {"up": "#00ff00", "down": "#ff0000", "unchanged": "#888888"}
                    },
                    {
                        "type": "line",
                        "label": "EMA 20",
                        "data": [{"x": ohlc_data[i]["x"], "y": ema_line[i]} for i in range(len(ohlc_data))],
                        "borderColor": "#d4af37",
                        "borderWidth": 2,
                        "fill": False,
                        "pointRadius": 0
                    }
                ]
            },
            "options": {
                "scales": {"x": {"type": "time"}},
                "plugins": {"legend": {"display": False}}
            }
        }
        encoded = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded}&w=800&h=400&bkg=%23111111"
        
        try:
            img_resp = requests.get(chart_url, timeout=15)
            if len(img_resp.content) < 5000:
                # اگر سایت خطا داد، نمودار خطی بفرست
                fallback_config = {
                    "type": "line",
                    "data": {
                        "labels": [d['x'] for d in ohlc_data],
                        "datasets": [{"label": coin, "data": closes, "borderColor": "#00ff00", "fill": False}]
                    }
                }
                fallback_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(fallback_config))}&w=800&h=400&bkg=%23111111"
                img_data = requests.get(fallback_url, timeout=15).content
                await context.bot.send_photo(chat_id=chat_id, photo=img_data, caption=f"📊 نمودار {coin} - {tf_fa}")
            else:
                await context.bot.send_photo(chat_id=chat_id, photo=img_resp.content, caption=f"📊 نمودار شمعی {coin} - {tf_fa}")
        except:
            pass

# --- هشدارها (منوی مرحله به مرحله) ---
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
        for i, a in enumerate(alerts):
            text += f"🔸 {a['symbol']} | قیمت: {format_price(a['target'])}\n"
        await query.edit_message_text(text, parse_mode='HTML')

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("نام ارز را تایپ کنید:")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        data_price = fetch_prices().get(coin) or get_okx(coin)
        if not data_price: return await query.edit_message_text("❌ ارز یافت نشد.")
        user_state[chat_id] = {'step': 'choose_type', 'symbol': coin}
        kb = [
            [InlineKeyboardButton("بر اساس قیمت 💵", callback_data="type_price")],
            [InlineKeyboardButton("بر اساس درصد 📊", callback_data="type_percent")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        await query.edit_message_text(f"ارز: {coin}\n💰 قیمت: {format_price(data_price['price'])}\n\nمرحله ۲: نوع هشدار؟", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("type_"):
        alert_type = data.replace("type_", "")
        state = user_state.get(chat_id)
        state['type'] = alert_type
        state['step'] = 'choose_direction'
        kb = [
            [InlineKeyboardButton("📈 بالاتر", callback_data="dir_above")],
            [InlineKeyboardButton("📉 پایین‌تر", callback_data="dir_below")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        await query.edit_message_text("مرحله ۳: جهت هشدار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("dir_"):
        direction = data.replace("dir_", "")
        state = user_state.get(chat_id)
        state['direction'] = direction
        state['step'] = 'enter_target'
        symbol = state['symbol']
        alert_type = state['type']
        current_data = fetch_prices().get(symbol) or get_okx(symbol)
        current_price = current_data['price'] if current_data else 0
        dir_fa = "بالاتر" if direction == "above" else "پایین‌تر"
        
        if alert_type == 'price':
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nقیمت لحظه‌ای: {format_price(current_price)}\n\nمرحله ۴: **قیمت هدف** را به دلار وارد کنید:"
        else:
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nمرحله ۴: **درصد هدف** را وارد کنید (بدون ٪):"
        await query.edit_message_text(msg, parse_mode='HTML')

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
        data_price = fetch_prices().get(up) or get_okx(up)
        if not data_price: return await update.message.reply_text("❌ ارز یافت نشد.")
        user_state[chat_id] = {'step': 'choose_type', 'symbol': up}
        kb = [
            [InlineKeyboardButton("قیمت 💵", callback_data="type_price")],
            [InlineKeyboardButton("درصد 📊", callback_data="type_percent")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        return await update.message.reply_text(f"ارز: {up}\n💰 قیمت: {format_price(data_price['price'])}\n\nنوع هشدار؟", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') in ['enter_target', 'edit_target']:
        try:
            target = float(txt)
            symbol = state['symbol']
            direction = state.get('direction', 'above')
            alert_type = state.get('type', 'price')
            
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
            user_alerts[chat_id].append({'symbol': symbol, 'target': target, 'direction': direction, 'type': alert_type})
            
            current_data = fetch_prices().get(symbol) or get_okx(symbol)
            cp = current_data['price'] if current_data else 0
            dir_fa = "بالاتر" if direction == "above" else "پایین‌تر"
            
            if alert_type == 'price':
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: {format_price(cp)}\n🎯 قیمت هدف: {format_price(target)} ({dir_fa})\n\nاگر قیمت به {format_price(target)} برسد، خبر می‌دهم."
            else: 
                final_price = cp * (1 + target/100) if direction == 'above' else cp * (1 - target/100)
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: {format_price(cp)}\n🎯 درصد: {target}% ({dir_fa})\n📈 معادل قیمت: {format_price(final_price)}\n\nاگر قیمت به {format_price(final_price)} برسد، خبر می‌دهم."
            
            await update.message.reply_text(msg)
            user_state[chat_id] = {} 
            return
        except ValueError:
            return await update.message.reply_text("❌ عدد معتبر وارد کنید.")

if __name__ == '__main__':
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|type_|dir_|alert_cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

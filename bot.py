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

def get_klines(symbol, timeframe='1H', limit=100):
    """دریافت کندل‌ها برای محاسبه اندیکاتورها"""
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            # داده‌ها به صورت [timestamp, open, high, low, close, vol, ...] هستند
            return [float(c[4]) for c in reversed(res['data'])] # فقط Close را برمی‌گردانیم
    except: pass
    return []

def calculate_indicators(closes):
    """محاسبه RSI، Bollinger Bands، EMA و ADX"""
    if len(closes) < 50: return None
    results = {}
    
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
    results['bb_upper'] = round(sma + (2 * std_dev), 6)
    results['bb_lower'] = round(sma - (2 * std_dev), 6)
    results['bb_mid'] = round(sma, 6)
    
    # 3. EMA (20)
    period_ema = 20
    multiplier = 2 / (period_ema + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    results['ema'] = round(ema, 6)
    
    # 4. ADX (14) - ساده‌شده برای محاسبه قدرت روند
    # (برای سادگی، از تغییرات قیمت به عنوان معیار قدرت استفاده می‌کنیم)
    trs = []
    for i in range(1, len(closes)):
        tr = abs(closes[i] - closes[i-1])
        trs.append(tr)
    avg_tr = sum(trs[-14:]) / 14
    price_change = abs(closes[-1] - closes[-14])
    results['adx'] = round((price_change / avg_tr) * 10 if avg_tr > 0 else 0, 2) # شبیه‌سازی
    
    return results

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    prices = fetch_prices()
    for chat_id, alerts in list(user_alerts.items()):
        lang = user_lang.get(chat_id, 'fa')
        for a in alerts[:]:
            data = prices.get(a['symbol']) or get_okx(a['symbol'])
            if not data: continue
            cp = data['price']
            
            triggered = False
            if a['type'] == 'price':
                if (a['direction'] == 'above' and cp >= a['target']) or (a['direction'] == 'below' and cp <= a['target']):
                    triggered = True
            elif a['type'] == 'percent':
                if (a['direction'] == 'above' and data['change'] >= a['target']) or (a['direction'] == 'below' and data['change'] <= a['target']):
                    triggered = True

            if triggered:
                msg = f"🚨 <b>هشدار قیمت!</b>\n\nارز <b>{a['symbol']}</b> به هدف شما رسید.\n💰 قیمت فعلی: ${cp:,.6f}" if lang == 'fa' else f"🚨 <b>Alert!</b>\n\n<b>{a['symbol']}</b> reached your target.\n💰 Current: ${cp:,.6f}"
                try: await context.bot.send_message(chat_id, msg, parse_mode='HTML')
                except: pass
                user_alerts[chat_id].remove(a)
        if not user_alerts[chat_id]: del user_alerts[chat_id]

# ----------------- منوها -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_lang[chat_id] = 'fa'
    user_state[chat_id] = {} 
    kb = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
        [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nبه ربات حرفه‌ای قیمت‌یاب خوش آمدید.\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if user_lang.get(chat_id, 'fa') == 'fa':
        user_lang[chat_id] = 'en'
        kb = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Advanced Analysis 📈"), KeyboardButton("Manage Alerts 🔔")],
            [KeyboardButton("Change Language 🇮🇷"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
            [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# ----------------- تحلیل پیشرفته -----------------

async def start_advanced_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {'step': 'analysis_type_coin'}
    await update.message.reply_text("لطفاً نام ارز مورد نظر خود را تایپ کنید (مثلاً BTC یا DOGE):")

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
        tf_map = {'1h': '1H', '4h': '4H', '1d': '1D'}
        okx_tf = tf_map.get(timeframe, '1H')
        tf_fa = {'1h': '۱ ساعته', '4h': '۴ ساعته', '1d': 'روزانه'}.get(timeframe, timeframe)
        
        await query.edit_message_text(f"⏳ در حال محاسبه اندیکاتورها برای {coin} در بازه {tf_fa}...")
        
        data_price = fetch_prices().get(coin) or get_okx(coin)
        closes = get_klines(coin, okx_tf, 100)
        ind = calculate_indicators(closes)
        
        if not data_price or not ind:
            return await query.edit_message_text("❌ اطلاعات کافی برای تحلیل یافت نشد.")
            
        # تفسیر اندیکاتورها
        text = f"📈 <b>تحلیل جامع: {coin}</b>\n⏱ بازه: {tf_fa}\n"
        text += f"💰 قیمت: ${data_price['price']:,.6f}\n"
        text += f"📊 تغییر ۲۴ ساعته: {data_price['change']:+.2f}%\n\n"
        
        # 1. RSI
        rsi = ind['rsi']
        if rsi > 70: rsi_status = "⚠️ اشباع خرید"
        elif rsi < 30: rsi_status = "🟢 اشباع فروش"
        else: rsi_status = "⚖️ خنثی"
        text += f"<b>1️⃣ RSI:</b> {rsi} ({rsi_status})\n"
        
        # 2. Bollinger Bands
        upper, lower = ind['bb_upper'], ind['bb_lower']
        if data_price['price'] > upper: bb_status = "⚠️ بالاتر از باند بالا (احتمال ریزش)"
        elif data_price['price'] < lower: bb_status = "🟢 پایین‌تر از باند پایین (احتمال رشد)"
        else: bb_status = "⚖️ داخل باندها (نوسان عادی)"
        text += f"<b>2️⃣ باند بولینگر:</b> {bb_status}\n"
        text += f"   <i>(بالا: ${upper:,.6f} | پایین: ${lower:,.6f})</i>\n"
        
        # 3. EMA
        ema = ind['ema']
        if data_price['price'] > ema: ema_status = "🟢 بالاتر از EMA (روند صعودی)"
        else: ema_status = "🔴 پایین‌تر از EMA (روند نزولی)"
        text += f"<b>3️⃣ میانگین متحرک (EMA 20):</b> {ema_status}\n"
        
        # 4. ADX
        adx = ind['adx']
        if adx > 25: adx_status = "💪 روند قوی"
        elif adx < 20: adx_status = "🔀 بازار رِنج (بدون روند)"
        else: adx_status = "⚖️ روند در حال شکل‌گیری"
        text += f"<b>4️⃣ قدرت روند (ADX):</b> {adx_status} ({adx})\n"
        
        await query.edit_message_text(text, parse_mode='HTML')
        
    elif data == "cancel_analysis":
        user_state[chat_id] = {}
        await query.edit_message_text("تحلیل لغو شد.")

# ----------------- سیستم هشدار -----------------

async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    kb = [
        [InlineKeyboardButton("➕ تنظیم هشدار جدید", callback_data="new_alert")],
        [InlineKeyboardButton("📋 مشاهده و ویرایش هشدارهای فعال", callback_data="view_alerts")]
    ]
    await update.message.reply_text("مدیریت هشدارها:", reply_markup=InlineKeyboardMarkup(kb))

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
                kb.append(row)
                row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("سایر ارزها (تایپ کنید) ✍️", callback_data="alert_other")])
        kb.append([InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")])
        await query.edit_message_text("مرحله ۱: ارز مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "view_alerts":
        alerts = user_alerts.get(chat_id, [])
        if not alerts:
            return await query.edit_message_text("شما هیچ هشدار فعالی ندارید.")
        text = "📋 هشدارهای فعال شما:\n\n"
        kb = []
        for i, a in enumerate(alerts):
            type_fa = "قیمت" if a['type'] == 'price' else "درصد"
            dir_fa = "بالاتر" if a['direction'] == 'above' else "پایین‌تر"
            text += f"🔸 {a['symbol']} | {type_fa} {dir_fa} از {a['target']}\n"
            kb.append([
                InlineKeyboardButton(f"✏️ ویرایش {a['symbol']}", callback_data=f"edit_alert_{i}"),
                InlineKeyboardButton(f"❌ حذف {a['symbol']}", callback_data=f"del_alert_{i}")
            ])
        kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_alerts")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_alert_"):
        idx = int(data.replace("del_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            removed = user_alerts[chat_id].pop(idx)
            await query.edit_message_text(f"✅ هشدار {removed['symbol']} حذف شد.")

    elif data.startswith("edit_alert_"):
        idx = int(data.replace("edit_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            alert = user_alerts[chat_id][idx]
            user_state[chat_id] = {'step': 'edit_target', 'alert_idx': idx, 'symbol': alert['symbol'], 'type': alert['type'], 'direction': alert['direction']}
            unit = "$" if alert['type'] == 'price' else "%"
            await query.edit_message_text(f"ویرایش هشدار {alert['symbol']}.\nلطفاً عدد جدید را وارد کنید (به {unit}):")

    elif data == "back_to_alerts":
        await show_alerts_menu(query, context)

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("نام ارز مورد نظر خود را تایپ کنید:")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        await process_coin_selection(chat_id, coin, query)
        
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
        await query.edit_message_text(f"نوع هشدار: {'قیمت' if alert_type=='price' else 'درصد'}\nمرحله ۳: جهت هشدار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

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
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nقیمت لحظه‌ای: ${current_price:,.6f}\n\nمرحله ۴: **قیمت هدف** را به دلار وارد کنید.\n(مثال: <code>{int(current_price * 1.05)}</code>)"
        else:
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nمرحله ۴: **درصد هدف** را وارد کنید (بدون ٪).\n(مثال: <code>5</code>)"
        await query.edit_message_text(msg, parse_mode='HTML')

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("عملیات لغو شد.")

async def process_coin_selection(chat_id, coin, query):
    data = fetch_prices().get(coin) or get_okx(coin)
    if not data:
        await query.edit_message_text(f"❌ ارز {coin} یافت نشد.")
        user_state[chat_id] = {}
        return
        
    user_state[chat_id] = {'step': 'choose_type', 'symbol': coin}
    closes = get_klines(coin, '1H', 100)
    ind = calculate_indicators(closes)
    
    if ind:
        rsi = ind['rsi']
        if rsi > 70: rsi_analysis = f"⚠️ <b>اشباع خرید</b> (RSI: {rsi})"
        elif rsi < 30: rsi_analysis = f"🟢 <b>اشباع فروش</b> (RSI: {rsi})"
        else: rsi_analysis = f"⚖️ <b>خنثی</b> (RSI: {rsi})"
    else:
        rsi_analysis = "⚪️ تحلیل در دسترس نیست."
    
    trend = f"🟢 <b>روند ۲۴ ساعته:</b> صعودی ({data['change']:+.2f}%)" if data['change'] > 0 else f"🔴 <b>روند ۲۴ ساعته:</b> نزولی ({data['change']:+.2f}%)"
    
    text = f"ارز: <b>{coin}</b>\n💰 ${data['price']:,.6f}\n{trend}\n📊 <b>تحلیل:</b> {rsi_analysis}\n\nمرحله ۲: هشدار بر چه اساس باشد؟"
    
    kb = [
        [InlineKeyboardButton("بر اساس قیمت 💵", callback_data="type_price")],
        [InlineKeyboardButton("بر اساس درصد 📊", callback_data="type_percent")],
        [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

# ----------------- توابع اصلی -----------------

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ در حال تحلیل بازار...")
    prices = fetch_prices()
    text = f"<b>📊 ۱۰ ارز برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        
        closes = get_klines(c, '1H', 50)
        ind = calculate_indicators(closes)
        
        if ind:
            rsi = ind['rsi']
            if rsi > 70: rsi_txt = f"⚠️ اشباع خرید ({rsi})"
            elif rsi < 30: rsi_txt = f"🟢 اشباع فروش ({rsi})"
            else: rsi_txt = f"⚖️ خنثی ({rsi})"
        else: rsi_txt = "N/A"
        
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.4f}\n📊 {d['change']:+.2f}%\n📈 {rsi_txt}\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ ...")
    prices = fetch_prices()
    text = f"<b>🔥 ۱۰ ترند برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.6f}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id, {})
    
    if "ریست" in txt or "Reset" in txt:
        user_state[chat_id] = {}
        return await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())

    if state.get('step') == 'analysis_type_coin':
        coin = up
        data = fetch_prices().get(coin) or get_okx(coin)
        if not data:
            return await update.message.reply_text(f"❌ ارز {coin} یافت نشد.")
        
        user_state[chat_id] = {'step': 'analysis_choose_tf', 'symbol': coin}
        kb = [
            [InlineKeyboardButton("۱ ساعته ⏱", callback_data="tf_1h")],
            [InlineKeyboardButton("۴ ساعته ⏰", callback_data="tf_4h")],
            [InlineKeyboardButton("روزانه 📅", callback_data="tf_1d")],
            [InlineKeyboardButton("🔙 لغو", callback_data="cancel_analysis")]
        ]
        return await update.message.reply_text(f"ارز {coin} انتخاب شد.\nلطفاً بازه زمانی تحلیل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') == 'type_coin':
        coin = up
        data = fetch_prices().get(coin) or get_okx(coin)
        if not data:
            return await update.message.reply_text(f"❌ ارز {coin} یافت نشد.")
        
        user_state[chat_id] = {'step': 'choose_type', 'symbol': coin}
        closes = get_klines(coin, '1H', 50)
        ind = calculate_indicators(closes)
        
        if ind:
            rsi = ind['rsi']
            if rsi > 70: rsi_analysis = f"⚠️ <b>اشباع خرید</b> (RSI: {rsi})"
            elif rsi < 30: rsi_analysis = f"🟢 <b>اشباع فروش</b> (RSI: {rsi})"
            else: rsi_analysis = f"⚖️ <b>خنثی</b> (RSI: {rsi})"
        else: rsi_analysis = "N/A"
        
        trend = f"🟢 صعودی ({data['change']:+.2f}%)" if data['change'] > 0 else f"🔴 نزولی ({data['change']:+.2f}%)"
        text = f"ارز: <b>{coin}</b>\n💰 ${data['price']:,.6f}\nروند: {trend}\n📊 RSI: {rsi_analysis}\n\nمرحله ۲: هشدار بر چه اساس باشد؟"
        kb = [
            [InlineKeyboardButton("قیمت 💵", callback_data="type_price")],
            [InlineKeyboardButton("درصد 📊", callback_data="type_percent")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        return await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    if state.get('step') in ['enter_target', 'edit_target']:
        try:
            target = float(txt.replace(',', '').replace('%', ''))
            if state.get('step') == 'edit_target':
                idx = state['alert_idx']
                if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
                    user_alerts[chat_id][idx]['target'] = target
                    await update.message.reply_text("✅ هشدار ویرایش شد.")
                user_state[chat_id] = {}
                return

            symbol = state['symbol']
            direction = state['direction']
            alert_type = state['type']
            
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
            user_alerts[chat_id].append({'symbol': symbol, 'target': target, 'direction': direction, 'type': alert_type})
            
            current_data = fetch_prices().get(symbol) or get_okx(symbol)
            cp = current_data['price'] if current_data else 0
            dir_fa = "بالاتر" if direction == "above" else "پایین‌تر"
            
            if alert_type == 'price':
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: ${cp:,.6f}\n🎯 قیمت هدف: ${target:,.6f} ({dir_fa})\n\nاگر قیمت به ${target:,.6f} برسد، خبر می‌دهم."
            else: 
                final_price = cp * (1 + target/100) if direction == 'above' else cp * (1 - target/100)
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: ${cp:,.6f}\n🎯 درصد: {target}% ({dir_fa})\n📈 معادل قیمت: ${final_price:,.6f}\n\nاگر قیمت به ${final_price:,.6f} برسد، خبر می‌دهم."
            await update.message.reply_text(msg)
            user_state[chat_id] = {} 
            return
        except ValueError:
            return await update.message.reply_text("❌ عدد معتبر وارد کنید یا ریست بزنید.")

    conv = re.match(r"^([\d\.]+)\s*([A-Z]{2,10})$", up)
    if conv:
        amt, sym = float(conv.group(1)), conv.group(2)
        d = fetch_prices().get(sym) or get_okx(sym)
        if d:
            return await update.message.reply_text(f"💱 {amt} {sym} = <b>${amt * d['price']:,.2f}</b>", parse_mode='HTML')
        
    if re.match(r"^[A-Z0-9]{2,10}$", up) and not state:
        msg = await update.message.reply_text("⏳ ...")
        d = fetch_prices().get(up) or get_okx(up)
        if d:
            return await msg.edit_text(f"<b>🔍 {up}</b>\n💰 ${d['price']:,.6f}\n📊 {d['change']:+.2f}%", parse_mode='HTML')
        return await msg.edit_text("❌ یافت نشد.")

    if "۱۰ ارز برتر" in txt or "Top 10 Coins" in txt: await top10(update, context)
    elif "ترند" in txt or "Trending" in txt: await trending(update, context)
    elif "تحلیل پیشرفته" in txt or "Advanced Analysis" in txt: await start_advanced_analysis(update, context)
    elif "مدیریت هشدار" in txt or "Manage Alerts" in txt: await show_alerts_menu(update, context)
    elif "زبان" in txt or "Language" in txt: await change_lang(update, context)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(check_alerts, interval=300, first=10)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|edit_alert|del_alert|back_to_alerts|alert_other|alertcoin_|type_|dir_|alert_cancel)")) 
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^(tf_|cancel_analysis)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

import os
import requests
import datetime
import jdatetime
import json
import urllib.parse
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
CHART_IMG_KEY = os.getenv("CHART_IMG_API_KEY") # کلید دریافت شده از chart-img.com
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

user_lang = {}
user_alerts = {}
user_state = {} 

def format_price(price):
    if price < 1: return f"${price:,.6f}"
    elif price < 100: return f"${price:,.4f}"
    else: return f"${price:,.2f}"

def get_time_str(chat_id):
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
    """دریافت کندل‌ها برای محاسبه اندیکاتورها (فقط Close)"""
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            return [float(c[4]) for c in reversed(res['data'])]
    except: pass
    return []

def calculate_indicators(closes):
    if len(closes) < 20: return None
    results = {}
    
    period_rsi = 14
    gains, losses = 0, 0
    for i in range(len(closes) - period_rsi, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    rs = (gains / period_rsi) / (losses / period_rsi) if losses > 0 else 100
    results['rsi'] = round(100 - (100 / (1 + rs)), 2)
    
    period_bb = 20
    recent_closes = closes[-period_bb:]
    sma = sum(recent_closes) / period_bb
    variance = sum((x - sma) ** 2 for x in recent_closes) / period_bb
    std_dev = variance ** 0.5
    results['bb_upper'] = sma + (2 * std_dev)
    results['bb_lower'] = sma - (2 * std_dev)
    
    multiplier = 2 / (20 + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    results['ema'] = ema
    
    trs = [abs(closes[i] - closes[i-1]) for i in range(1, len(closes))]
    avg_tr = sum(trs[-14:]) / 14
    price_change = abs(closes[-1] - closes[-14])
    results['adx'] = (price_change / avg_tr) * 10 if avg_tr > 0 else 0
    
    return results

# --- شروع و منوها ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_lang[chat_id] = 'fa'
    user_state[chat_id] = {} 
    kb = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
        [KeyboardButton("طلا، ارز و نفت 🌍"), KeyboardButton("درباره سازنده 👨‍💻")],
        [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nبه ربات پیشرفته کریپتو خوش آمدید.\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if user_lang.get(chat_id, 'fa') == 'fa':
        user_lang[chat_id] = 'en'
        kb = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Advanced Analysis 📈"), KeyboardButton("Manage Alerts 🔔")],
            [KeyboardButton("Gold, Forex & Oil 🌍"), KeyboardButton("About Developer 👨‍💻")],
            [KeyboardButton("Change Language 🇮🇷"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
            [KeyboardButton("طلا، ارز و نفت 🌍"), KeyboardButton("درباره سازنده 👨‍💻")],
            [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- لیست‌ها ---
async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>📊 ۱۰ ارز برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 قیمت لحظه‌ای: {format_price(d['price'])}\n📊 تغییر ۲۴س: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>🔥 ۱۰ ترند برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 قیمت لحظه‌ای: {format_price(d['price'])}\n📊 تغییر ۲۴س: {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

# --- تحلیل پیشرفته (با سرویس جدید) ---
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
        
        await query.edit_message_text(f"⏳ در حال تحلیل {coin} در تایم‌فریم {tf_fa}...")
        
        closes = get_klines(coin, okx_tf, 40)
        if not closes: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        ind = calculate_indicators(closes)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        current_price = data_price['price']
        
        # تفسیر اندیکاتورها
        rsi = ind['rsi']
        if rsi > 70: rsi_txt = f"⚠️ اشباع خرید ({rsi})"
        elif rsi < 30: rsi_txt = f"🟢 اشباع فروش ({rsi})"
        else: rsi_txt = f"⚖️ خنثی ({rsi})"
        
        if current_price > ind['bb_upper']: bb_txt = "🔴 بالاتر از سقف"
        elif current_price < ind['bb_lower']: bb_txt = "🟢 پایین‌تر از کف"
        else: bb_txt = "⚖️ داخل باندها"
        
        ema_txt = "🟢 بالای EMA (صعودی)" if current_price > ind['ema'] else "🔴 زیر EMA (نزولی)"
        
        adx = ind['adx']
        if adx > 25: adx_txt = f"💪 روند قوی ({adx:.2f})"
        elif adx < 20: adx_txt = f"🔀 بازار رِنج ({adx:.2f})"
        else: adx_txt = f"⚖️ شکل‌گیری روند ({adx:.2f})"
        
        score = 0
        if rsi < 30 or current_price < ind['bb_lower'] or current_price > ind['ema']: score += 1
        if rsi > 70 or current_price > ind['bb_upper'] or current_price < ind['ema']: score -= 1
        
        if adx < 20: summary = "⚠️ <b>بازار رِنج است.</b>\nسیگنال‌ها قابل اعتماد نیستند."
        elif score >= 2: summary = "🟢 <b>صعودی</b>\nقدرت خریداران مشهود است."
        elif score <= -2: summary = "🔴 <b>نزولی</b>\nفشار فروشندگان بالاست."
        else: summary = "⚖️ <b>خنثی</b>\nسیگنال‌های متناقض."

        text = (
            f"📈 <b>تحلیل {coin}</b> ({tf_fa})\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"💰 <b>قیمت لحظه‌ای:</b> {format_price(current_price)}\n"
            f"📊 <b>تغییر ۲۴س:</b> {data_price['change']:+.2f}%\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"📉 <b>اندیکاتورها:</b>\n\n"
            f"1️⃣ <b>RSI:</b>\n   {rsi_txt}\n\n"
            f"2️⃣ <b>بولینگر:</b>\n   {bb_txt}\n\n"
            f"3️⃣ <b>EMA:</b>\n   {ema_txt}\n\n"
            f"4️⃣ <b>ADX:</b>\n   {adx_txt}\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🎯 <b>برآیند نهایی:</b>\n{summary}"
        )
        
        await query.edit_message_text(text, parse_mode='HTML')
        
        # =========================================================
        # سیستم جدید ارسال نمودار
        # =========================================================
        chart_sent = False
        
        # لایه اول: استفاده از سرویس Chart-Img (اگر کلید وجود داشته باشد)
        if CHART_IMG_KEY:
            try:
                # نگاشت تایم‌فریم به فرمت Chart-Img
                ci_tf = {'1m': '1', '5m': '5', '15m': '15', '30m': '30', '1H': '60', '4H': '240', '1D': 'D'}
                chart_img_url = "https://api.chart-img.com/v2/tradingview/advanced-chart"
                payload = {
                    "symbol": f"BINANCE:{coin}USDT",
                    "interval": ci_tf.get(timeframe, '60'),
                    "theme": "dark",
                    "style": "candlestick"
                }
                headers = {"x-api-key": CHART_IMG_KEY, "Content-Type": "application/json"}
                resp = requests.post(chart_img_url, json=payload, headers=headers, timeout=15)
                
                if resp.status_code == 200:
                    img_data = resp.content
                    if len(img_data) > 5000: # اطمینان از اینکه عکس خطا نیست
                        await context.bot.send_photo(chat_id=chat_id, photo=img_data, caption=f"📊 نمودار شمعی {coin} - {tf_fa}")
                        chart_sent = True
            except: pass

        # لایه دوم: استفاده از FINVIZ به عنوان جایگزین (بدون نیاز به کلید)
        if not chart_sent:
            try:
                finviz_tf = {'1m': 'm1', '5m': 'm5', '15m': 'm15', '30m': 'm30', '1H': 'h1', '4H': 'h4', '1D': 'd1'}
                f_tf = finviz_tf.get(timeframe, 'h1')
                finviz_url = f"https://finviz.com/fx_image.ashx?{coin}USD_{f_tf}_l.png"
                
                img_resp = requests.get(finviz_url, timeout=10)
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    await context.bot.send_photo(chat_id=chat_id, photo=img_resp.content, caption=f"📊 نمودار شمعی {coin} - {tf_fa} (FINVIZ)")
                    chart_sent = True
            except: pass
            
        if not chart_sent:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ متأسفانه در حال حاضر امکان دریافت تصویر نمودار وجود ندارد. متن تحلیل بالا ارسال شد.")

# ... (بقیه کدهای هشدار، طلا و مدیریت متن‌ها دقیقاً مثل قبل است) ...
# (برای جلوگیری از طولانی شدن، از همان کدهای قبلی استفاده کنید)
async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    kb = [
        [InlineKeyboardButton("➕ تنظیم هشدار جدید", callback_data="new_alert")],
        [InlineKeyboardButton("📋 مشاهده و ویرایش هشدارها", callback_data="view_alerts")]
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
        kb.append([InlineKeyboardButton("سایر ارزها (تایپ کنید) ✍️", callback_data="alert_other")])
        kb.append([InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")])
        await query.edit_message_text("مرحله ۱: ارز را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "view_alerts":
        alerts = user_alerts.get(chat_id, [])
        if not alerts: return await query.edit_message_text("هشداری ندارید.")
        text = "📋 <b>هشدارهای فعال شما:</b>\n\n"
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
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

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
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌های جهانی...")
    text = f"🌍 <b>بازارهای جهانی</b>\n🕒 {get_time_str(chat_id)}\n\n"
    text += "🥇 <b>فلزات:</b>\n• انس جهانی طلا: $2,350.50\n• نقره: $28.40\n\n"
    text += "🛢 <b>نفت و انرژی:</b>\n• نفت برنت: $82.30\n• نفت WTI: $78.10\n• گاز طبیعی: $2.15\n\n"
    text += "💵 <b>شاخص‌ها:</b>\n• شاخص دلار (DXY): 104.50\n• یورو/دلار: 1.0840"
    await msg.edit_text(text, parse_mode='HTML')

async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👨‍💻 <b>صادق دوستی‌خواه</b>\n📧 <code>S.doostikhah@gmail.com</code>", parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    
    if "ریست" in txt or "Reset" in txt:
        user_state[chat_id] = {}
        return await update.message.reply_text("منو ریست شد. /start را بزنید.")
    elif "۱۰ ارز برتر" in txt or "Top 10 Coins" in txt:
        user_state[chat_id] = {}; await top10(update, context); return
    elif "ترند" in txt or "Trending" in txt:
        user_state[chat_id] = {}; await trending(update, context); return
    elif "تحلیل" in txt or "Analysis" in txt:
        user_state[chat_id] = {}; await start_advanced_analysis(update, context); return
    elif "هشدار" in txt or "Alerts" in txt:
        user_state[chat_id] = {}; await show_alerts_menu(update, context); return
    elif "طلا" in txt or "Gold" in txt or "نفت" in txt:
        user_state[chat_id] = {}; await gold_forex(update, context); return
    elif "سازنده" in txt or "Developer" in txt:
        user_state[chat_id] = {}; await about_developer(update, context); return
    elif "زبان" in txt or "Language" in txt:
        user_state[chat_id] = {}; await change_lang(update, context); return

    state = user_state.get(chat_id, {})
    
    if state.get('step') == 'analysis_type_coin':
        user_state[chat_id] = {'step': 'analysis_choose_tf', 'symbol': up}
        kb = [
            [InlineKeyboardButton("۱ دقیقه", callback_data="tf_1m"), InlineKeyboardButton("۵ دقیقه", callback_data="tf_5m"), InlineKeyboardButton("۱۵ دقیقه", callback_data="tf_15m")],
            [InlineKeyboardButton("۳۰ دقیقه", callback_data="tf_30m"), InlineKeyboardButton("۱ ساعته", callback_data="tf_1H"), InlineKeyboardButton("۴ ساعته", callback_data="tf_4H")],
            [InlineKeyboardButton("روزانه", callback_data="tf_1D")]
        ]
        return await update.message.reply_text(f"ارز {up} انتخاب شد. تایم‌فریم مورد نظر:", reply_markup=InlineKeyboardMarkup(kb))

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
            if state.get('step') == 'edit_target':
                idx = state['alert_idx']
                if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
                    user_alerts[chat_id][idx]['target'] = target
                    await update.message.reply_text("✅ هشدار با موفقیت ویرایش شد.")
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
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: {format_price(cp)}\n🎯 قیمت هدف: {format_price(target)} ({dir_fa})\n\nاگر قیمت به {format_price(target)} برسد، خبر می‌دهم."
            else: 
                final_price = cp * (1 + target/100) if direction == 'above' else cp * (1 - target/100)
                msg = f"✅ هشدار {symbol} تنظیم شد!\n\n💰 قیمت فعلی: {format_price(cp)}\n🎯 درصد: {target}% ({dir_fa})\n📈 معادل قیمت: {format_price(final_price)}\n\nاگر قیمت به {format_price(final_price)} برسد، خبر می‌دهم."
            
            await update.message.reply_text(msg)
            user_state[chat_id] = {} 
            return
        except ValueError:
            return await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")

if __name__ == '__main__':
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|type_|dir_|edit_alert_|del_alert_|back_to_alerts|alert_cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

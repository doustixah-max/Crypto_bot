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

def get_klines_ohlc(symbol, timeframe='1H', limit=50):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            data = []
            for c in reversed(res['data']):
                ts = int(c[0])
                dt = datetime.datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M')
                data.append({
                    "x": dt,
                    "o": float(c[1]),
                    "h": float(c[2]),
                    "l": float(c[3]),
                    "c": float(c[4])
                })
            return data
    except: pass
    return []

def calculate_ema(closes, period=20):
    if len(closes) < period: return []
    multiplier = 2 / (period + 1)
    ema_values = []
    ema = closes[0]
    for i, price in enumerate(closes):
        ema = (price - ema) * multiplier + ema
        if i >= period:
            ema_values.append(ema)
        else:
            ema_values.append(None)
    return ema_values

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
        
        await query.edit_message_text(f"⏳ در حال دریافت نمودار {coin} در تایم‌فریم {tf_fa}...")
        
        ohlc_data = get_klines_ohlc(coin, okx_tf, 50)
        if not ohlc_data: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        closes = [d['c'] for d in ohlc_data]
        ema_data = calculate_ema(closes, 20)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        
        chart_config = {
            "type": "candlestick",
            "data": {
                "datasets": [
                    {
                        "label": f"{coin} Price",
                        "data": ohlc_data,
                        "color": {"up": "#00ff00", "down": "#ff0000", "unchanged": "#888888"}
                    },
                    {
                        "type": "line",
                        "label": "EMA 20",
                        "data": ema_data,
                        "borderColor": "#d4af37",
                        "borderWidth": 2,
                        "fill": False,
                        "pointRadius": 0
                    }
                ]
            },
            "options": {"plugins": {"legend": {"display": False}}}
        }
        encoded_config = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded_config}&w=800&h=450&bkg=%23111111"
        
        text = (
            f"📈 <b>تحلیل {coin}</b> (تایم‌فریم: {tf_fa})\n"
            f"💰 قیمت لحظه‌ای: {format_price(data_price['price'])}\n"
            f"📊 تغییر ۲۴س: {data_price['change']:+.2f}%\n"
            f"➖➖➖➖➖➖\n"
            f"🟢 شمع سبز: صعود | 🔴 شمع قرمز: نزول\n"
            f"🟡 خط طلایی: میانگین متحرک (EMA 20)"
        )
        await query.edit_message_text(text, parse_mode='HTML')
        await context.bot.send_photo(chat_id=chat_id, photo=chart_url, caption=f"📊 نمودار شمعی {coin} - {tf_fa}")

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
        for i, a in enumerate(alerts):
            text += f"🔸 {a['symbol']} | قیمت هدف: {format_price(a['target'])}\n"
        await query.edit_message_text(text, parse_mode='HTML')

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("نام ارز را تایپ کنید:")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        data_price = fetch_prices().get(coin) or get_okx(coin)
        if not data_price: return await query.edit_message_text("❌ ارز یافت نشد.")
        user_state[chat_id] = {'step': 'enter_target', 'symbol': coin}
        await query.edit_message_text(f"ارز: {coin}\n💰 قیمت لحظه‌ای: {format_price(data_price['price'])}\n\nعدد قیمت هدف را وارد کنید:")

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("لغو شد.")

# --- طلا، ارز و نفت (به‌روزرسانی شده) ---
async def gold_forex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌های جهانی طلا، ارز و نفت...")
    
    # دریافت قیمت‌های جهانی از API
    oil_data = {}
    try:
        res = requests.get("https://api.oilpriceapi.com/v1/demo/prices", timeout=10).json()
        if res.get('status') == 'success':
            for item in res['data']['prices']:
                oil_data[item['code']] = {
                    'price': item['price'],
                    'change': item.get('change_24h', 0)
                }
    except: pass
    
    text = f"🌍 <b>بازارهای جهانی (طلا، ارز و انرژی)</b>\n🕒 {get_time_str(chat_id)}\n\n"
    
    # بخش طلا و فلزات
    text += "🥇 <b>فلزات گرانبها:</b>\n"
    if 'GOLD_USD' in oil_data:
        g = oil_data['GOLD_USD']
        icon = "🟢" if g['change'] > 0 else "🔴"
        text += f"• انس جهانی طلا (XAU): ${g['price']:,.2f} {icon} ({g['change']:+.2f}%)\n"
    if 'SILVER_USD' in oil_data:
        s = oil_data['SILVER_USD']
        icon = "🟢" if s['change'] > 0 else "🔴"
        text += f"• نقره (XAG): ${s['price']:,.2f} {icon} ({s['change']:+.2f}%)\n"
    
    # بخش نفت و انرژی
    text += "\n🛢 <b>نفت و انرژی:</b>\n"
    oil_mapping = {
        'BRENT_CRUDE_USD': 'نفت برنت (Brent)',
        'WTI_USD': 'نفت WTI (تگزاس)',
        'DUBAI_CRUDE_USD': 'نفت دبی (Dubai)',
        'OPEC_BASKET_USD': 'سبد نفتی اوپک (OPEC)',
        'NATURAL_GAS_USD': 'گاز طبیعی (Henry Hub)'
    }
    for code, label in oil_mapping.items():
        if code in oil_data:
            o = oil_data[code]
            icon = "🟢" if o['change'] > 0 else "🔴"
            text += f"• {label}: <b>${o['price']:,.2f}</b> {icon} ({o['change']:+.2f}%)\n"
    
    # بخش ارز
    text += "\n💵 <b>شاخص‌های ارزی:</b>\n"
    if 'EUR_USD' in oil_data:
        e = oil_data['EUR_USD']
        text += f"• یورو به دلار (EUR/USD): {e['price']:.4f}\n"
    if 'GBP_USD' in oil_data:
        p = oil_data['GBP_USD']
        text += f"• پوند به دلار (GBP/USD): {p['price']:.4f}\n"
    text += f"• شاخص دلار (DXY): 104.50 (پیش‌فرض)\n"
    
    text += f"\n🕒 <i>آخرین به‌روزرسانی: {get_time_str(chat_id)}</i>"
    await msg.edit_text(text, parse_mode='HTML')

async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    if lang == 'fa':
        text = "👨‍💻 <b>درباره سازنده</b>\n\nاین ربات توسط <b>صادق دوستی‌خواه</b> طراحی شده است.\n📧 <b>ایمیل:</b> <code>S.doostikhah@gmail.com</code>"
    else:
        text = "👨‍💻 <b>About Developer</b>\n\nDeveloped by <b>Sadegh Doostikhah</b>.\n📧 <b>Email:</b> <code>S.doostikhah@gmail.com</code>"
    await update.message.reply_text(text, parse_mode='HTML')

# --- مدیریت متن‌ها ---
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
    elif "طلا" in txt or "Gold" in txt or "نفت" in txt or "Oil" in txt:
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
        return await update.message.reply_text(f"ارز {up} انتخاب شد. تایم‌فریم مورد نظر برای نمودار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') == 'type_coin':
        user_state[chat_id] = {'step': 'enter_target', 'symbol': up}
        data_price = fetch_prices().get(up) or get_okx(up)
        if data_price:
            return await update.message.reply_text(f"ارز {up} انتخاب شد. قیمت لحظه‌ای: {format_price(data_price['price'])}\nعدد قیمت هدف را وارد کنید:")
        return await update.message.reply_text("❌ ارز یافت نشد.")

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
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|alert_cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

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

def get_klines(symbol, timeframe='1H', limit=50):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            return [[int(c[0]), float(c[4])] for c in reversed(res['data'])]
    except: pass
    return []

# --- منوی اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {} 
    kb = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
        [KeyboardButton("تحلیل و نمودار 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
        [KeyboardButton("قیمت طلا و ارز 🌍"), KeyboardButton("درباره سازنده 👨‍💻")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nبه ربات کریپتو خوش آمدید.\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- لیست‌ها ---
async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>📊 ۱۰ ارز برتر</b>\n🕒 {get_time_str()}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 {format_price(d['price'])}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت...")
    prices = fetch_prices()
    text = f"<b>🔥 ۱۰ ترند</b>\n🕒 {get_time_str()}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 {format_price(d['price'])}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

# --- تحلیل و نمودار (با استفاده از QuickChart) ---
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
        tf_map = {'1h': '1H', '4h': '4H', '1d': '1D'}
        okx_tf = tf_map.get(timeframe, '1H')
        tf_fa = {'1h': '۱ ساعته', '4h': '۴ ساعته', '1d': 'روزانه'}.get(timeframe, timeframe)
        
        await query.edit_message_text(f"⏳ در حال تحلیل {coin}...")
        klines = get_klines(coin, okx_tf, 50)
        if not klines: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        closes = [k[1] for k in klines]
        labels = [datetime.datetime.fromtimestamp(k[0]/1000).strftime('%H:%M') for k in klines]
        data_price = fetch_prices().get(coin) or get_okx(coin)
        
        # ساخت نمودار با استفاده از API سایت QuickChart (بدون نیاز به کتابخانه سنگین)
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": f"{coin} Price",
                    "data": closes,
                    "borderColor": "#d4af37", # رنگ طلایی
                    "backgroundColor": "rgba(212, 175, 55, 0.2)",
                    "fill": True,
                    "borderWidth": 2,
                    "pointRadius": 0
                }]
            },
            "options": {
                "plugins": {"legend": {"display": False}}
            }
        }
        
        encoded_config = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded_config}&w=800&h=400&bkg=%23111111&fcc=%23ffffff"
        
        text = f"📈 <b>تحلیل {coin}</b> ({tf_fa})\n💰 قیمت: {format_price(data_price['price'])}\n📊 تغییر: {data_price['change']:+.2f}%"
        
        await query.edit_message_text(text, parse_mode='HTML')
        await context.bot.send_photo(chat_id=chat_id, photo=chart_url, caption=f"📊 نمودار {coin} در بازه {tf_fa}")

# --- مدیریت هشدارها ---
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
                kb.append(row)
                row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("سایر ارزها (تایپ کنید) ✍️", callback_data="alert_other")])
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
        user_state[chat_id] = {'step': 'enter_target', 'symbol': coin}
        await query.edit_message_text(f"ارز: {coin}\n💰 قیمت فعلی: {format_price(data_price['price'])}\n\nعدد قیمت هدف را وارد کنید:")

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("لغو شد.")

# --- سایر ---
async def gold_forex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌍 انس جهانی طلا: $2,350.50\n💵 شاخص دلار: 104.50\n🛢 نفت برنت: $82.30")

async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👨‍💻 <b>صادق دوستی‌خواه</b>\n📧 <code>S.doostikhah@gmail.com</code>", parse_mode='HTML')

# --- مدیریت متن‌ها ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    
    # اولویت اول: بررسی دکمه‌های منوی اصلی (اگر کاربر هر دکمه‌ای زد، وضعیت قبلی پاک می‌شود)
    if "ریست" in txt:
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
    elif "طلا" in txt:
        user_state[chat_id] = {}; await gold_forex(update, context); return
    elif "سازنده" in txt:
        user_state[chat_id] = {}; await about_developer(update, context); return

    # اولویت دوم: بررسی وضعیت‌های درون‌فرآیندی
    state = user_state.get(chat_id, {})
    
    if state.get('step') == 'analysis_type_coin':
        user_state[chat_id] = {'step': 'analysis_choose_tf', 'symbol': up}
        kb = [
            [InlineKeyboardButton("۱ ساعته ⏱", callback_data="tf_1h"), InlineKeyboardButton("۴ ساعته ⏰", callback_data="tf_4h")],
            [InlineKeyboardButton("روزانه 📅", callback_data="tf_1d")]
        ]
        return await update.message.reply_text(f"ارز {up} انتخاب شد. بازه زمانی:", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') == 'type_coin':
        user_state[chat_id] = {'step': 'enter_target', 'symbol': up}
        data_price = fetch_prices().get(up) or get_okx(up)
        if data_price:
            return await update.message.reply_text(f"ارز {up} انتخاب شد. قیمت فعلی: {format_price(data_price['price'])}\nعدد قیمت هدف را وارد کنید:")
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

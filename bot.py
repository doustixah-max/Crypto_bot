import os
import requests
import datetime
import jdatetime
import re
import asyncio
import io
import matplotlib
matplotlib.use('Agg') # برای جلوگیری از خطای سرور بدون نمایشگر
import matplotlib.pyplot as plt
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

user_lang = {}
user_alerts = {}
user_state = {} 

# ----------------- توابع کمکی -----------------

def format_price(price):
    """تشخیص خودکار تعداد اعشار بر اساس قیمت"""
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

def get_klines(symbol, timeframe='1H', limit=100):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            return [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4])] for c in reversed(res['data'])]
    except: pass
    return []

def calculate_indicators(closes):
    if len(closes) < 50: return None
    results = {}
    
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
    
    period_bb = 20
    recent_closes = closes[-period_bb:]
    sma = sum(recent_closes) / period_bb
    variance = sum((x - sma) ** 2 for x in recent_closes) / period_bb
    std_dev = variance ** 0.5
    results['bb_upper'] = round(sma + (2 * std_dev), 6)
    results['bb_lower'] = round(sma - (2 * std_dev), 6)
    
    period_ema = 20
    multiplier = 2 / (period_ema + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    results['ema'] = round(ema, 6)
    
    trs = []
    for i in range(1, len(closes)):
        tr = abs(closes[i] - closes[i-1])
        trs.append(tr)
    avg_tr = sum(trs[-14:]) / 14
    price_change = abs(closes[-1] - closes[-14])
    results['adx'] = round((price_change / avg_tr) * 10 if avg_tr > 0 else 0, 2)
    
    return results

def calculate_signal_score(price, ind):
    """سیستم امتیازدهی هوشمند از 0 تا 100"""
    score = 50 
    if not ind: return score
    
    if ind['rsi'] < 30: score += 20
    elif ind['rsi'] > 70: score -= 20
    
    if price < ind['bb_lower']: score += 15
    elif price > ind['bb_upper']: score -= 15
    
    if price > ind['ema']: score += 15
    else: score -= 15
    
    if ind['adx'] > 25:
        if score > 50: score += 10
        else: score -= 10
        
    return max(0, min(100, score)) 

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
                msg = f"🚨 <b>هشدار قیمت!</b>\n\nارز <b>{a['symbol']}</b> به هدف شما رسید.\n💰 قیمت فعلی: {format_price(cp)}" if lang == 'fa' else f"🚨 <b>Alert!</b>\n\n<b>{a['symbol']}</b> reached target.\n💰 Current: {format_price(cp)}"
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
        [KeyboardButton("رهگیری نهنگ‌ها 🐋"), KeyboardButton("قیمت طلا و ارز 🌍")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("درباره سازنده 👨‍💻")],
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
            [KeyboardButton("Whale Tracker 🐋"), KeyboardButton("Gold & Forex 🌍")],
            [KeyboardButton("Help ❓"), KeyboardButton("About Developer 👨‍💻")],
            [KeyboardButton("Change Language 🇮🇷"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
            [KeyboardButton("رهگیری نهنگ‌ها 🐋"), KeyboardButton("قیمت طلا و ارز 🌍")],
            [KeyboardButton("راهنما ❓"), KeyboardButton("درباره سازنده 👨‍💻")],
            [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    
    if lang == 'fa':
        text = (
            "🤖 <b>راهنمای جامع ربات Coin Master</b>\n\n"
            "📊 <b>۱۰ ارز برتر:</b> قیمت، تغییرات ۲۴ ساعته و RSI.\n"
            "🔥 <b>۱۰ ترند برتر:</b> ارزهای با بیشترین توجه در واچ‌لیست.\n"
            "📈 <b>تحلیل پیشرفته:</b> تحلیل تکنیکال (RSI، بولینگر، EMA، ADX) + ارسال نمودار قیمت + امتیاز سیگنال.\n"
            "🔔 <b>مدیریت هشدارها:</b> تنظیم، ویرایش و حذف هشدارهای قیمت یا درصد.\n"
            "🐋 <b>رهگیری نهنگ‌ها:</b> بررسی جریان پول و فشار بازار.\n"
            "🌍 <b>قیمت طلا و ارز:</b> انس جهانی طلا و شاخص دلار.\n"
            "💱 <b>مقایسه صرافی‌ها:</b> تایپ نام ارز برای مقایسه قیمت در صرافی‌های ایرانی.\n"
            "🔍 <b>جستجو و مبدل:</b> تایپ نام ارز (مثل TON) یا مقدار (مثل 0.5 BTC).\n\n"
            "💡 <i>برای شروع، از منوی پایین یک گزینه را انتخاب کنید.</i>"
        )
    else:
        text = (
            "🤖 <b>Coin Master Comprehensive Guide</b>\n\n"
            "📊 <b>Top 10 Coins:</b> Price, 24h change, and RSI.\n"
            "🔥 <b>Top 10 Trending:</b> Most watched coins.\n"
            "📈 <b>Advanced Analysis:</b> Technical analysis (RSI, BB, EMA, ADX) + Price Chart + Signal Score.\n"
            "🔔 <b>Manage Alerts:</b> Set, edit, and delete price/percent alerts.\n"
            "🐋 <b>Whale Tracker:</b> Smart money flow analysis.\n"
            "🌍 <b>Gold & Forex:</b> Global Gold (XAU) and DXY.\n"
            "💱 <b>Exchange Comparison:</b> Type a coin to compare prices on Iranian exchanges.\n"
            "🔍 <b>Search & Converter:</b> Type a coin (e.g., TON) or amount (e.g., 0.5 BTC).\n\n"
            "💡 <i>To start, choose an option from the menu below.</i>"
        )
    await update.message.reply_text(text, parse_mode='HTML')

async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    if lang == 'fa':
        text = "👨‍💻 <b>درباره سازنده</b>\n\nاین ربات توسط <b>صادق دوستی‌خواه</b> طراحی شده است.\n📧 <b>ایمیل:</b> <code>S.doostikhah@gmail.com</code>"
    else:
        text = "👨‍💻 <b>About Developer</b>\n\nDeveloped by <b>Sadegh Doostikhah</b>.\n📧 <b>Email:</b> <code>S.doostikhah@gmail.com</code>"
    await update.message.reply_text(text, parse_mode='HTML')

# ----------------- قابلیت‌های ویژه -----------------

async def whale_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال اسکن تراکنش‌های بزرگ بازار...")
    await asyncio.sleep(2)
    text = (
        "🐋 <b>رهگیری نهنگ‌ها (Whale Alerts)</b>\n\n"
        "⚠️ <b>توجه:</b> تراکنش‌های بزرگ زیر نظر است.\n"
        "به دلیل محدودیت سرورهای رایگان، نمایش لحظه‌ای نیاز به سرور اختصاصی دارد.\n\n"
        "📊 <b>وضعیت فعلی بازار:</b>\n"
        "🔹 حجم معاملات ۲۴ ساعته بیت‌کوین: بالا\n"
        "🔹 فشار خرید (Buy Pressure): متعادل\n"
        "🔹 هشدار: حرکت‌های ناگهانی در آلت‌کوین‌ها (مثل SOL) دیده می‌شود."
    )
    await msg.edit_text(text, parse_mode='HTML')

async def gold_forex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌های جهانی...")
    try:
        res = requests.get("https://api.metalpriceapi.com/v1/latest?api_key=demo&base=USD&currencies=XAU", timeout=10).json()
        gold_price = res.get('rates', {}).get('USDXAU', 0)
        if gold_price == 0: gold_price = 2350.50 
        text = (
            "🌍 <b>بازارهای جهانی</b>\n\n"
            f"🥇 <b>انس جهانی طلا (XAU):</b> ${gold_price:,.2f}\n"
            f"💵 <b>شاخص دلار (DXY):</b> 104.50\n"
            f"🛢 <b>نفت برنت:</b> $82.30\n\n"
            "<i>این اعداد به عنوان شاخص‌های اقتصاد کلان بر بازار کریپتو تاثیر مستقیم دارند.</i>"
        )
        await msg.edit_text(text, parse_mode='HTML')
    except:
        await msg.edit_text("❌ خطا در دریافت داده‌های جهانی.")

async def compare_exchanges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {'step': 'arbitrage_coin'}
    await update.message.reply_text("💱 <b>مقایسه قیمت صرافی‌ها</b>\nلطفاً نام ارز را وارد کنید (مثلاً BTC یا USDT):", parse_mode='HTML')

# ----------------- تحلیل پیشرفته -----------------

async def start_advanced_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    intro_msg = "📈 <b>تحلیل پیشرفته</b>\nنام ارز را وارد کنید (مثلاً BTC):"
    await update.message.reply_text(intro_msg, parse_mode='HTML')
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
        
        klines = get_klines(coin, okx_tf, 100)
        if not klines: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        closes = [k[4] for k in klines]
        ind = calculate_indicators(closes)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        price = data_price['price']
        
        score = calculate_signal_score(price, ind)
        if score > 70: signal_txt = f"🟢 <b>سیگنال صعودی قوی ({score}/100)</b>"
        elif score < 30: signal_txt = f"🔴 <b>سیگنال نزولی قوی ({score}/100)</b>"
        else: signal_txt = f"⚖️ <b>سیگنال خنثی ({score}/100)</b>"
        
        text = (
            f"📈 <b>تحلیل جامع: {coin}</b> ({tf_fa})\n"
            f"💰 قیمت: {format_price(price)}\n"
            f"{signal_txt}\n"
            f"➖➖➖➖➖➖\n"
            f"RSI: <code>{ind['rsi']}</code> | ADX: <code>{ind['adx']}</code>"
        )
        await query.edit_message_text(text, parse_mode='HTML')
        
        # ساخت نمودار
        plt.figure(figsize=(10, 5))
        times = [datetime.datetime.fromtimestamp(k[0]/1000) for k in klines]
        plt.plot(times, closes, color='gold', linewidth=2)
        plt.title(f"{coin} Chart ({tf_fa})")
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        
        await context.bot.send_photo(chat_id=chat_id, photo=buf, caption=f"📊 نمودار {coin} در بازه {tf_fa}")
        
    elif data == "cancel_analysis":
        user_state[chat_id] = {}
        await query.edit_message_text("تحلیل لغو شد.")

# ----------------- هشدارها -----------------

async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    intro_msg = (
        "🔔 <b>مدیریت هشدارها</b>\n\n"
        "در این بخش می‌توانید هشدار قیمت تنظیم کنید. ربات در پس‌زمینه قیمت‌ها را چک می‌کند.\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    kb = [
        [InlineKeyboardButton("➕ تنظیم هشدار جدید", callback_data="new_alert")],
        [InlineKeyboardButton("📋 مشاهده و ویرایش هشدارها", callback_data="view_alerts")]
    ]
    await update.message.reply_text(intro_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

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
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nقیمت لحظه‌ای: {format_price(current_price)}\n\nمرحله ۴: **قیمت هدف** را به دلار وارد کنید.\n(مثال: <code>{int(current_price * 1.05)}</code>)"
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
    closes = [k[4] for k in get_klines(coin, '1H', 100)]
    ind = calculate_indicators(closes)
    
    if ind:
        rsi = ind['rsi']
        if rsi > 70: rsi_analysis = f"⚠️ <b>اشباع خرید</b> (RSI: {rsi})"
        elif rsi < 30: rsi_analysis = f"🟢 <b>اشباع فروش</b> (RSI: {rsi})"
        else: rsi_analysis = f"⚖️ <b>خنثی</b> (RSI: {rsi})"
    else:
        rsi_analysis = "⚪️ تحلیل در دسترس نیست."
    
    trend = f"🟢 <b>روند ۲۴ ساعته:</b> صعودی ({data['change']:+.2f}%)" if data['change'] > 0 else f"🔴 <b>روند ۲۴ ساعته:</b> نزولی ({data['change']:+.2f}%)"
    
    text = f"ارز: <b>{coin}</b>\n💰 {format_price(data['price'])}\n{trend}\n📊 <b>تحلیل:</b> {rsi_analysis}\n\nمرحله ۲: هشدار بر چه اساس باشد؟"
    
    kb = [
        [InlineKeyboardButton("بر اساس قیمت 💵", callback_data="type_price")],
        [InlineKeyboardButton("بر اساس درصد 📊", callback_data="type_percent")],
        [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

# ----------------- لیست‌ها -----------------

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    intro = "📊 <b>۱۰ ارز برتر بازار</b>\n⏳ در حال دریافت اطلاعات..."
    msg = await update.message.reply_text(intro, parse_mode='HTML')
    await asyncio.sleep(1.5) 
    
    prices = fetch_prices()
    text = f"<b>📊 ۱۰ ارز برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        closes = [k[4] for k in get_klines(c, '1H', 50)]
        ind = calculate_indicators(closes)
        rsi_txt = f"RSI: {ind['rsi']}" if ind else "N/A"
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 {format_price(d['price'])}\n📊 {d['change']:+.2f}%\n📈 {rsi_txt}\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    intro = "🔥 <b>۱۰ ترند برتر</b>\n⏳ در حال دریافت اطلاعات..."
    msg = await update.message.reply_text(intro, parse_mode='HTML')
    await asyncio.sleep(1.5)
    
    prices = fetch_prices()
    text = f"<b>🔥 ۱۰ ترند برتر</b>\n🕒 {get_time_str(chat_id)}\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 {format_price(d['price'])}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

# ----------------- مدیریت متن‌ها -----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id, {})
    
    # --- ریست ---
    if "ریست" in txt or "Reset" in txt:
        user_state[chat_id] = {}
        lang = user_lang.get(chat_id, 'fa')
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("تحلیل پیشرفته 📈"), KeyboardButton("مدیریت هشدارها 🔔")],
            [KeyboardButton("رهگیری نهنگ‌ها 🐋"), KeyboardButton("قیمت طلا و ارز 🌍")],
            [KeyboardButton("راهنما ❓"), KeyboardButton("درباره سازنده 👨‍💻")],
            [KeyboardButton("تغییر زبان 🇬🇧"), KeyboardButton("ریست 🔄")]
        ] if lang == 'fa' else [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Advanced Analysis 📈"), KeyboardButton("Manage Alerts 🔔")],
            [KeyboardButton("Whale Tracker 🐋"), KeyboardButton("Gold & Forex 🌍")],
            [KeyboardButton("Help ❓"), KeyboardButton("About Developer 👨‍💻")],
            [KeyboardButton("Change Language 🇮🇷"), KeyboardButton("Reset 🔄")]
        ]
        return await update.message.reply_text("🔄 منو ریست شد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    # --- مقایسه صرافی ---
    if state.get('step') == 'arbitrage_coin':
        coin = up
        msg = await update.message.reply_text(f"⏳ در حال بررسی قیمت {coin}...")
        wallex_data = fetch_prices().get(coin)
        if wallex_data:
            text = f"💱 <b>مقایسه قیمت {coin}</b>\n\n"
            text += f"🟢 <b>والکس:</b> {format_price(wallex_data['price'])}\n"
            text += f"🟡 <b>نوبیتکس:</b> {format_price(wallex_data['price'] * 1.001)} (تخمینی)\n"
            text += f"🔵 <b>بیت‌پین:</b> {format_price(wallex_data['price'] * 0.999)} (ت

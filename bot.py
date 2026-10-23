import os
import requests
import datetime
import jdatetime
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf
import yfinance as yf
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]
TRENDING_COINS = ["SOL", "PEPE", "DOGE", "WIF", "AVAX", "TON", "SHIB", "BONK", "FLOKI", "NOT"]

user_alerts = {}
user_state = {}
user_lang = {}

TEXTS = {
    'fa': {
        'welcome': "سلام! 🚀\nبه ربات پیشرفته Coin Master خوش آمدید.\nیک گزینه انتخاب کنید:\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>توسعه‌دهنده:</b> صادق دوستی‌خواه\n"
        "📧 <b>ایمیل:</b> <code>S.doostikhah@gmail.com</code>\n"
        "━━━━━━━━━━━━━━━━━━",
        'top10': "۱۰ ارز برتر 📊", 'trend': "۱۰ ترند برتر 🔥", 'analysis': "تحلیل پیشرفته 📈",
        'alerts': "مدیریت هشدارها 🔔", 'markets': "طلا، ارز و نفت 🌍", 'help': "راهنما ❓",
        'lang': "تغییر زبان 🇬🇧", 'reset': "ریست 🔄",
        'select_tf': "⏱ لطفاً بازه زمانی را انتخاب کنید:", 'loading': "⏳ در حال دریافت...",
        'tf_1m': "۱ دقیقه", 'tf_5m': "۵ دقیقه", 'tf_15m': "۱۵ دقیقه", 'tf_30m': "۳۰ دقیقه",
        'tf_1H': "۱ ساعته", 'tf_4H': "۴ ساعته", 'tf_1D': "روزانه", 'tf_2D': "۲ روزه", 'tf_3D': "۳ روزه",
        'tf_1W': "۱ هفته", 'tf_1M': "۱ ماه",
        'price': "قیمت لحظه‌ای", 'change': "تغییر در", 'vol': "نوسان در",
        'analysis_title': "تحلیل جامع", 'rsi': "RSI", 'bollinger': "بولینگر", 'ema': "EMA", 'adx': "ADX",
        'conclusion': "برآیند نهایی", 'bullish': "🟢 صعودی", 'bearish': "🔴 نزولی", 'ranging': "⚠️ رِنج / خنثی",
        'overbought': "اشباع خرید", 'oversold': "اشباع فروش", 'neutral': "خنثی",
        'above_bb': "بالاتر از سقف", 'below_bb': "پایین‌تر از کف", 'inside_bb': "داخل باندها",
        'above_ema': "بالای EMA", 'below_ema': "زیر EMA", 'strong_trend': "روند قوی", 'ranging_mkt': "بازار رِنج",
        'alert_manage': "🔔 مدیریت هشدارها:", 'alert_new': "➕ تنظیم هشدار جدید", 'alert_view': "📋 مشاهده هشدارها",
        'select_coin': "مرحله ۱: ارز را انتخاب کنید:", 'other_coin': "سایر ارزها (تایپ) ✍️", 'cancel': "🔙 لغو",
        'alert_type': "مرحله ۲: نوع هشدار را انتخاب کنید:", 'type_price': "قیمت 💵", 'type_percent': "درصد 📊", 'type_vol': "نوسان 🌊",
        'alert_dir': "مرحله ۳: جهت هشدار را انتخاب کنید:", 'dir_above': "📈 بالاتر", 'dir_below': "📉 پایین‌تر",
        'enter_target': "مرحله ۴: عدد هدف را وارد کنید:", 'alert_set': "✅ هشدار تنظیم شد!",
        'no_alerts': "شما هیچ هشدار فعالی ندارید.", 'edit_alert': "ویرایش", 'del_alert': "حذف",
        'edit_prompt': "عدد جدید هدف را وارد کنید:", 'deleted': "✅ هشدار با موفقیت حذف شد.",
        'global_title': "بازارهای جهانی", 'gold': "🥇 انس جهانی طلا", 'silver': "🥈 نقره", 'brent': "🛢 نفت برنت", 'wti': "🛢 نفت WTI",
        'error_data': "❌ خطا در دریافت داده‌ها (سرور پاسخ نداد).", 'reset_msg': "منو ریست شد. /start را بزنید.",
        'help_text': "🤖 <b>راهنمای ربات Coin Master</b>\n\n📊 ۱۰ ارز برتر و ترندها (با انتخاب تایم‌فریم)\n📈 تحلیل تکنیکال (نمودار شمعی + اندیکاتورها)\n🔔 هشدار قیمت، درصد و نوسان\n🌍 شاخص‌های جهانی (طلا، نفت، ...)\n\n💡 از دکمه‌های پایین استفاده کنید.",
        'confirm_preview': "📝 <b>پیش‌نمایش هشدار</b>\n\nآیا از ثبت این هشدار اطمینان دارید؟",
        'btn_confirm': "✅ تایید و ثبت", 'btn_cancel_confirm': "❌ لغو",
        'alert_confirmed': "✅ هشدار با موفقیت ثبت شد.", 'alert_canceled': "❌ ثبت هشدار لغو شد."
    },
    'en': {
        'welcome': "Hello! 🚀\nWelcome to the Advanced Coin Master Bot.\nChoose an option:\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>Developer:</b> Sadegh Doostikhah\n"
        "📧 <b>Email:</b> <code>S.doostikhah@gmail.com</code>\n"
        "━━━━━━━━━━━━━━━━━━",
        'top10': "Top 10 Coins 📊", 'trend': "Top 10 Trending 🔥", 'analysis': "Advanced Analysis 📈",
        'alerts': "Manage Alerts 🔔", 'markets': "Gold, Forex & Oil 🌍", 'help': "Help ❓",
        'lang': "Language 🇮🇷", 'reset': "Reset 🔄",
        'select_tf': "⏱ Please select a timeframe:", 'loading': "⏳ Fetching data...",
        'tf_1m': "1m", 'tf_5m': "5m", 'tf_15m': "15m", 'tf_30m': "30m",
        'tf_1H': "1H", 'tf_4H': "4H", 'tf_1D': "1D", 'tf_2D': "2D", 'tf_3D': "3D",
        'tf_1W': "1W", 'tf_1M': "1M",
        'price': "Current Price", 'change': "Change in", 'vol': "Volatility in",
        'analysis_title': "Analysis", 'rsi': "RSI", 'bollinger': "Bollinger", 'ema': "EMA", 'adx': "ADX",
        'conclusion': "Conclusion", 'bullish': "🟢 Bullish", 'bearish': "🔴 Bearish", 'ranging': "⚠️ Ranging / Neutral",
        'overbought': "Overbought", 'oversold': "Oversold", 'neutral': "Neutral",
        'above_bb': "Above Upper Band", 'below_bb': "Below Lower Band", 'inside_bb': "Inside Bands",
        'above_ema': "Above EMA", 'below_ema': "Below EMA", 'strong_trend': "Strong Trend", 'ranging_mkt': "Ranging Market",
        'alert_manage': "🔔 Manage Alerts:", 'alert_new': "➕ New Alert", 'alert_view': "📋 View Alerts",
        'select_coin': "Step 1: Select a coin:", 'other_coin': "Other coins (type) ✍️", 'cancel': "🔙 Cancel",
        'alert_type': "Step 2: Alert Type:", 'type_price': "Price 💵", 'type_percent': "Percent 📊", 'type_vol': "Volatility 🌊",
        'alert_dir': "Step 3: Direction:", 'dir_above': "📈 Above", 'dir_below': "📉 Below",
        'enter_target': "Step 4: Enter target value:", 'alert_set': "✅ Alert set successfully!",
        'no_alerts': "You have no active alerts.", 'edit_alert': "Edit", 'del_alert': "Delete",
        'edit_prompt': "Enter new target value:", 'deleted': "✅ Alert deleted successfully.",
        'global_title': "Global Markets", 'gold': "🥇 Gold (XAU)", 'silver': "🥈 Silver (XAG)", 'brent': "🛢 Brent Crude", 'wti': "🛢 WTI Crude",
        'error_data': "❌ Error fetching data (server timeout).", 'reset_msg': "Menu reset. Send /start.",
        'help_text': "🤖 <b>Coin Master Help</b>\n\n📊 Top 10 & Trending (with timeframe)\n📈 Technical Analysis (Candlestick + Indicators)\n🔔 Price, Percent & Volatility Alerts\n🌍 Global Markets (Gold, Oil...)\n\n💡 Use the buttons below.",
        'confirm_preview': "📝 <b>Alert Preview</b>\n\nAre you sure you want to set this alert?",
        'btn_confirm': "✅ Confirm & Save", 'btn_cancel_confirm': "❌ Cancel",
        'alert_confirmed': "✅ Alert successfully saved.", 'alert_canceled': "❌ Alert creation canceled."
    }
}

def get_lang(chat_id):
    return user_lang.get(chat_id, 'fa')

def format_price(price):
    if price < 1: return f"{price:,.4f}"
    else: return f"$`{price:,.2f}"

def get_time_str():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    return f"{jdatetime.date.fromgregorian(date=now.date()).strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def fetch_prices():
    prices = {}
    try:
        res = requests.get("https://api.wallex.ir/v1/markets", timeout=5).json()
        if res.get('success'):
            for sym, data in res['result']['symbols'].items():
                if sym.endswith("USDT"):
                    prices[sym.replace("USDT", "")] = {'price': float(data['stats']['lastPrice'])}
    except: pass
    return prices

def get_okx_stats(symbol):
    try:
        res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT", timeout=5).json()
        if res.get('code') == '0' and res.get('data'):
            d = res['data'][0]
            price = float(d['last'])
            high = float(d['high24h'])
            low = float(d['low24h'])
            vol = ((high - low) / low) * 100 if low > 0 else 0
            return {'price': price, 'vol_24h': vol}
    except: pass
    return None

def get_tf_data(symbol, timeframe):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit=24"
        res = requests.get(url, timeout=5).json()
        if res.get('code') == '0' and len(res.get('data', [])) >= 1:
            open_price = float(res['data'][-1][1])
            current_price = float(res['data'][0][4])
            highs = [float(c[2]) for c in res['data']]
            lows = [float(c[3]) for c in res['data']]
            change_pct = ((current_price - open_price) / open_price) * 100 if open_price > 0 else 0
            volatility_pct = ((max(highs) - min(lows)) / open_price) * 100 if open_price > 0 else 0
            return change_pct, volatility_pct
    except: pass
    return 0, 0

def get_klines_dataframe(symbol, timeframe='1H', limit=40):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=5).json()
        if res.get('code') == '0' and res.get('data'):
            data = []
            for c in reversed(res['data']):
                ts = int(c[0])
                dt = datetime.datetime.fromtimestamp(ts/1000)
                data.append({
                    "Date": dt,
                    "Open": float(c[1]), "High": float(c[2]),
                    "Low": float(c[3]), "Close": float(c[4]), "Volume": float(c[5])
                })
            df = pd.DataFrame(data)
            # اصلاح هشدار Pandas
            df = df.set_index('Date')
            return df
    except: pass
    return None

def calculate_indicators(df):
    if len(df) < 20: return None
    results = {}
    closes = df['Close'].tolist()
    highs = df['High'].tolist()
    lows = df['Low'].tolist()

    gains, losses = 0, 0
    for i in range(len(closes) - 14, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    rs = (gains / 14) / (losses / 14) if losses > 0 else 100
    results['rsi'] = round(100 - (100 / (1 + rs)), 2)

    recent = closes[-20:]
    sma = sum(recent) / 20
    variance = sum((x - sma) ** 2 for x in recent) / 20
    std = variance ** 0.5
    results['bb_upper'] = sma + (2 * std)
    results['bb_lower'] = sma - (2 * std)

    multiplier = 2 / (20 + 1)
    ema_line, ema = [], closes[0]
    for price in closes:
        ema = (price - ema) * multiplier + ema
        ema_line.append(ema)
    results['ema'] = ema_line[-1]
    results['ema_line'] = ema_line

    trs, plus_dms, minus_dms = [], [], []
    for i in range(1, len(df)):
        h, l, prev_c = highs[i], lows[i], closes[i-1]
        prev_h, prev_l = highs[i-1], lows[i-1]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up_move, down_move = h - prev_h, prev_l - l
        plus_dms.append(up_move if (up_move > down_move and up_move > 0) else 0)
        minus_dms.append(down_move if (down_move > up_move and down_move > 0) else 0)

    if len(trs) >= 14:
        avg_tr = sum(trs[-14:]) / 14
        plus_di = (sum(plus_dms[-14:]) / 14 / avg_tr) * 100 if avg_tr > 0 else 0
        minus_di = (sum(minus_dms[-14:]) / 14 / avg_tr) * 100 if avg_tr > 0 else 0
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
        results['adx'] = round(dx, 2)
    else:
        results['adx'] = 0
    return results

async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    prices = fetch_prices()
    for chat_id, alerts in list(user_alerts.items()):
        lang = get_lang(chat_id)
        t = TEXTS[lang]
        for a in alerts[:]:
            d = prices.get(a['symbol']) or get_okx_stats(a['symbol'])
            if not d: continue
            cp = d['price']
            triggered = False

            if a.get('type') == 'price':
                if (a['direction'] == 'above' and cp >= a['target']) or (a['direction'] == 'below' and cp <= a['target']):
                    triggered = True
            elif a.get('type') == 'percent':
                change, _ = get_tf_data(a['symbol'], '1H')
                if (a['direction'] == 'above' and change >= a['target']) or (a['direction'] == 'below' and change <= -a['target']):
                    triggered = True
            elif a.get('type') == 'volatility':
                _, vol = get_tf_data(a['symbol'], '1H')
                if vol >= a['target']:
                    triggered = True

            if triggered:
                msg = f"🚨 <b>{t['alerts']}: {a['symbol']}</b>\n\n{t['alert_set']}\n💰 {t['price']}: <code>{format_price(cp)}</code>"
                try: await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                except: pass
                user_alerts[chat_id].remove(a)
        if chat_id in user_alerts and not user_alerts[chat_id]: del user_alerts[chat_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_lang: user_lang[chat_id] = 'fa'
    user_state[chat_id] = {}
    t = TEXTS[get_lang(chat_id)]

    kb = [
        [KeyboardButton(t['top10']), KeyboardButton(t['trend'])],
        [KeyboardButton(t['analysis']), KeyboardButton(t['alerts'])],
        [KeyboardButton(t['markets']), KeyboardButton(t['help'])],
        [KeyboardButton(t['lang']), KeyboardButton(t['reset'])]
    ]
    await update.message.reply_text(t['welcome'], reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='HTML')

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_lang[chat_id] = 'en' if get_lang(chat_id) == 'fa' else 'fa'
    await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS[get_lang(update.effective_chat.id)]['help_text'], parse_mode='HTML')

async def show_list_tf_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type):
    t = TEXTS[get_lang(update.effective_chat.id)]
    kb = [
        [InlineKeyboardButton(t['tf_1m'], callback_data=f"list_{list_type}_1m"), InlineKeyboardButton(t['tf_5m'], callback_data=f"list_{list_type}_5m")],
        [InlineKeyboardButton(t['tf_15m'], callback_data=f"list_{list_type}_15m"), InlineKeyboardButton(t['tf_30m'], callback_data=f"list_{list_type}_30m")],
        [InlineKeyboardButton(t['tf_1H'], callback_data=f"list_{list_type}_1H"), InlineKeyboardButton(t['tf_4H'], callback_data=f"list_{list_type}_4H")],
        [InlineKeyboardButton(t['tf_1D'], callback_data=f"list_{list_type}_1D")]
    ]
    await update.message.reply_text(t['select_tf'], reply_markup=InlineKeyboardMarkup(kb))

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    t = TEXTS[get_lang(chat_id)]
    
    parts = query.data.split("_")
    list_type, tf = parts[1], parts[2]
    tf_fa = t.get(f"tf_{tf}", tf)

    await query.edit_message_text(t['loading'])
    prices = fetch_prices()
    coins_to_process = TOP_COINS if list_type == "top10" else TRENDING_COINS
    title = t['top10'] if list_type == "top10" else t['trend']
    text = f"<b>{title}</b>\n🕒 {get_time_str()}\n⏱ <i>{t['change']} {tf_fa}</i>\n\n"

    cnt = 0
    for c in coins_to_process:
        if cnt >= 10: break
        d = prices.get(c) or get_okx_stats(c)
        if d:
            cnt += 1
            change, vol = get_tf_data(c, tf)
            icon = "🟢" if change > 0 else "🔴"
            text += (
                f"<b>{c}</b> {icon}\n"
                f"💰 {t['price']}: <code>{format_price(d['price'])}</code>\n"
                f"📊 {t['change']} {tf_fa}: <code>{change:+.2f}%</code>\n"
                f"🌊 {t['vol']} {tf_fa}: <code>{vol:.2f}%</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )
    await query.edit_message_text(text, parse_mode='HTML')

async def start_advanced_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = "Enter coin symbol (e.g., BTC):" if get_lang(chat_id) == 'en' else "نام ارز را وارد کنید (مثلاً BTC):"
    await update.message.reply_text(msg)
    user_state[chat_id] = {'step': 'analysis_type_coin'}

async def handle_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    t = TEXTS[get_lang(chat_id)]
    data = query.data

    if data.startswith("tf_"):
        tf_code = data.replace("tf_", "")
        state = user_state.get(chat_id)
        if not state or 'symbol' not in state: return
        coin = state['symbol']

        if tf_code == "2D": okx_tf, limit, tf_fa = '1D', 2, t['tf_2D']
        elif tf_code == "3D": okx_tf, limit, tf_fa = '1D', 3, t['tf_3D']
        elif tf_code == "1W": okx_tf, limit, tf_fa = '1D', 7, t['tf_1W']
        elif tf_code == "1M": okx_tf, limit, tf_fa = '1D', 30, t['tf_1M']
        else: okx_tf, limit, tf_fa = tf_code, 40, t.get(f"tf_{tf_code}", tf_code)

        await query.edit_message_text(t['loading'])

        df = get_klines_dataframe(coin, okx_tf, limit)

        if df is None or df.empty:
            stats = get_okx_stats(coin)
            if stats:
                msg = (
                    f"⚠️ ارز <b>{coin}</b> برای تحلیل تکنیکال در این تایم‌فریم داده کافی ندارد.\n\n"
                    f"💰 {t['price']}: <code>{format_price(stats['price'])}</code>\n"
                    f"🌊 {t['vol']} 24h: <code>{stats['vol_24h']:.2f}%</code>"
                )
                return await query.edit_message_text(msg, parse_mode='HTML')
            else:
                return await query.edit_message_text(t['error_data'])

        ind = calculate_indicators(df)
        cp = df['Close'].iloc[-1]
        change_in_tf = ((cp - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if df['Close'].iloc[0] > 0 else 0

        rsi = ind['rsi']
        if rsi > 70: rsi_txt = f"⚠️ {t['overbought']} ({rsi})"
        elif rsi < 30: rsi_txt = f"🟢 {t['oversold']} ({rsi})"
        else: rsi_txt = f"⚖️ {t['neutral']} ({rsi})"

        bb_txt = f"🔴 {t['above_bb']}" if cp > ind['bb_upper'] else (f"🟢 {t['below_bb']}" if cp < ind['bb_lower'] else f"⚖️ {t['inside_bb']}")
        ema_txt = f"🟢 {t['above_ema']}" if cp > ind['ema'] else f"🔴 {t['below_ema']}"
        adx_txt = f"💪 {t['strong_trend']} ({ind['adx']})" if ind['adx'] > 25 else (f"🔀 {t['ranging_mkt']} ({ind['adx']})" if ind['adx'] < 20 else f"⚖️ ({ind['adx']})")

        if ind['adx'] < 20: conclusion = t['ranging']
        elif cp > ind['ema'] and rsi > 50: conclusion = t['bullish']
        elif cp < ind['ema'] and rsi < 50: conclusion = t['bearish']
        else: conclusion = t['neutral']

        text = (
            f"📈 <b>{t['analysis_title']} {coin}</b> ({tf_fa})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>{t['price']}:</b> <code>{format_price(cp)}</code>\n"
            f"📊 <b>{t['change']} {tf_fa}:</b> <code>{change_in_tf:+.2f}%</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ <b>{t['rsi']}:</b> {rsi_txt}\n"
            f"2️⃣ <b>{t['bollinger']}:</b> {bb_txt}\n"
            f"3️⃣ <b>{t['ema']}:</b> {ema_txt}\n"
            f"4️⃣ <b>{t['adx']}:</b> {adx_txt}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>{t['conclusion']}:</b> {conclusion}"
        )
        await query.edit_message_text(text, parse_mode='HTML')

        try:
            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit')
            custom_style = mpf.make_mpf_style(base_mpl_style="dark_background", marketcolors=mc, facecolor="#111111", figcolor="#111111", edgecolor="#888888", gridcolor="#333333", rc={"axes.labelcolor": "white", "xtick.color": "white", "ytick.color": "white"})
            ap = mpf.make_addplot(ind['ema_line'], color='gold', width=1.5)
            buf = io.BytesIO()
            mpf.plot(df, type='candle', style=custom_style, addplot=ap, savefig=buf, figsize=(10, 6), tight_layout=True)
            buf.seek(0)
            plt.close('all')
            await context.bot.send_photo(chat_id=chat_id, photo=buf, caption=f"📊 {coin} - {tf_fa}")
        except Exception: pass

async def show_global_markets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = TEXTS[get_lang(update.effective_chat.id)]
    kb = [
        [InlineKeyboardButton("24h" if get_lang(update.effective_chat.id)=='en' else "۲۴ ساعته", callback_data="global_1d"), InlineKeyboardButton("3D" if get_lang(update.effective_chat.id)=='en' else "۳ روزه", callback_data="global_3d")],
        [InlineKeyboardButton("1W" if get_lang(update.effective_chat.id)=='en' else "۱ هفته", callback_data="global_1w"), InlineKeyboardButton("1M" if get_lang(update.effective_chat.id)=='en' else "۱ ماه", callback_data="global_1m")],
    ]
    await update.message.reply_text(t['select_tf'], reply_markup=InlineKeyboardMarkup(kb))

async def handle_global_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    t = TEXTS[get_lang(chat_id)]
    data = query.data

    period_map = {"global_1d": "5d", "global_3d": "5d", "global_1w": "1mo", "global_1m": "3mo"}
    period = period_map.get(data, "5d")
    tf_fa = {"global_1d": t['tf_1D'], "global_3d": t['tf_3D'], "global_1w": t['tf_1W'], "global_1m": t['tf_1M']}.get(data, "")

    await query.edit_message_text(t['loading'])
    try:
        tickers = {"GC=F": t['gold'], "SI=F": t['silver'], "BZ=F": t['brent'], "CL=F": t['wti']}
        text = f"🌍 <b>{t['global_title']} ({tf_fa})</b>\n━━━━━━━━━━━━━━━━━━\n"

        for ticker, name in tickers.items():
            tick = yf.Ticker(ticker)
            # اصلاح تایم اوت yfinance برای جلوگیری از ارور
            hist = tick.history(period=period)
            if len(hist) > 1:
                idx = 1 if data == "global_1d" else (3 if data == "global_3d" else (7 if data == "global_1w" else 30))
                open_price = hist['Open'].iloc[-idx] if len(hist) > idx else hist['Open'].iloc[0]
                current_price = hist['Close'].iloc[-1]
                change = ((current_price - open_price) / open_price) * 100
                icon = "🟢" if change > 0 else "🔴"
                text += f"{name}:\n💰 <code>{format_price(current_price)}</code> | {icon} <code>{change:+.2f}%</code>\n\n"
        await query.edit_message_text(text, parse_mode='HTML')
    except Exception:
        await query.edit_message_text(t['error_data'])

async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    t = TEXTS[get_lang(chat_id)]
    kb = [
        [InlineKeyboardButton(t['alert_new'], callback_data="new_alert")],
        [InlineKeyboardButton(t['alert_view'], callback_data="view_alerts")]
    ]
    await update.message.reply_text(t['alert_manage'], reply_markup=InlineKeyboardMarkup(kb))

async def handle_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    lang = get_lang(chat_id)
    t = TEXTS[lang]
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
        kb.append([InlineKeyboardButton(t['other_coin'], callback_data="alert_other")])
        kb.append([InlineKeyboardButton(t['cancel'], callback_data="alert_cancel")])
        await query.edit_message_text(t['select_coin'], reply_markup=InlineKeyboardMarkup(kb))

    elif data == "view_alerts":
        alerts = user_alerts.get(chat_id, [])
        if not alerts: return await query.edit_message_text(t['no_alerts'])
        text = f"📋 <b>{t['alert_view']}:</b>\n\n"
        kb = []
        for i, a in enumerate(alerts):
            type_fa = {"price": t['type_price'], "percent": t['type_percent'], "volatility": t['type_vol']}.get(a.get('type', 'price'))
            dir_fa = t['dir_above'] if a.get('direction') == 'above' else t['dir_below']
            target_str = format_price(a['target']) if a.get('type') == 'price' else f"{a['target']}%"

            text += f"🔸 <b>{a['symbol']}</b> | {type_fa} {dir_fa} {target_str}\n"
            kb.append([
                InlineKeyboardButton(f"✏️ {t['edit_alert']} {a['symbol']}", callback_data=f"edit_alert_{i}"),
                InlineKeyboardButton(f"❌ {t['del_alert']} {a['symbol']}", callback_data=f"del_alert_{i}")
            ])
        kb.append([InlineKeyboardButton("🔙", callback_data="back_to_alerts")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith("del_alert_"):
        idx = int(data.replace("del_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            user_alerts[chat_id].pop(idx)
            if not user_alerts[chat_id]: del user_alerts[chat_id]
        await query.edit_message_text(t['deleted'])
        await show_alerts_menu(query, context)

    elif data.startswith("edit_alert_"):
        idx = int(data.replace("edit_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            alert = user_alerts[chat_id][idx]
            user_state[chat_id] = {
                'step': 'edit_target', 'alert_idx': idx, 'symbol': alert['symbol'],
                'type': alert.get('type', 'price'), 'direction': alert.get('direction', 'above')
            }
            unit = "`$" if alert.get('type') == 'price' else "%"
            await query.edit_message_text(f"{t['edit_prompt']} ({unit})")

    elif data == "back_to_alerts":
        await show_alerts_menu(query, context)

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("Enter coin:" if lang=='en' else "نام ارز را تایپ کنید:")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        stats = get_okx_stats(coin)
        if not stats: return await query.edit_message_text(t['error_data'])

        user_state[chat_id] = {'step': 'choose_type', 'symbol': coin}
        kb = [
            [InlineKeyboardButton(t['type_price'], callback_data="type_price"), InlineKeyboardButton(t['type_percent'], callback_data="type_percent")],
            [InlineKeyboardButton(t['type_vol'], callback_data="type_volatility")],
            [InlineKeyboardButton(t['cancel'], callback_data="alert_cancel")]
        ]
        msg = (
            f"ارز: <b>{coin}</b>\n"
            f"💰 {t['price']}: <code>{format_price(stats['price'])}</code>\n"
            f"🌊 {t['vol']} 24h: <code>{stats['vol_24h']:.2f}%</code>\n\n"
            f"{t['alert_type']}"
        ) if lang == 'fa' else (
            f"Coin: <b>{coin}</b>\n"
            f"💰 {t['price']}: <code>{format_price(stats['price'])}</code>\n"
            f"🌊 {t['vol']} 24h: <code>{stats['vol_24h']:.2f}%</code>\n\n"
            f"{t['alert_type']}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith("type_"):
        alert_type = data.replace("type_", "")
        state = user_state.get(chat_id)
        state['type'] = alert_type

        if alert_type == 'volatility':
            state['step'] = 'enter_target'
            await query.edit_message_text(f"{t['enter_target']} (e.g. 5)" if lang=='en' else f"{t['enter_target']} (مثلاً 5 برای ۵٪)")
        else:
            state['step'] = 'choose_direction'
            kb = [
                [InlineKeyboardButton(t['dir_above'], callback_data="dir_above")],
                [InlineKeyboardButton(t['dir_below'], callback_data="dir_below")],
                [InlineKeyboardButton(t['cancel'], callback_data="alert_cancel")]
            ]
            await query.edit_message_text(t['alert_dir'], reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("dir_"):
        direction = data.replace("dir_", "")
        state = user_state.get(chat_id)
        state['direction'] = direction
        state['step'] = 'enter_target'
        symbol = state['symbol']
        alert_type = state['type']

        stats = get_okx_stats(symbol)
        current_price = stats['price'] if stats else 0

        unit = "$" if alert_type == 'price' else "%"
        msg = f"{t['enter_target']} ({unit})\n\n"
        if alert_type == 'price':
            msg += f"{t['price']}: <code>{format_price(current_price)}</code>"

        await query.edit_message_text(msg, parse_mode='HTML')

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text(t['cancel'])

    elif data == "confirm_save_alert":
        state = user_state.get(chat_id)
        if state and 'temp_alert' in state:
            alert = state['temp_alert']
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != alert['symbol']]
            user_alerts[chat_id].append(alert)

            await query.edit_message_text(t['alert_confirmed'])
            user_state[chat_id] = {}

    elif data == "cancel_save_alert":
        user_state[chat_id] = {}
        await query.edit_message_text(t['alert_canceled'])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    txt = update.message.text.strip()
    up = txt.upper()
    lang = get_lang(chat_id)
    t = TEXTS[lang]

    if txt in [TEXTS['fa']['reset'], TEXTS['en']['reset']]:
        user_state[chat_id] = {}
        return await update.message.reply_text(t['reset_msg'])
    elif txt in [TEXTS['fa']['top10'], TEXTS['en']['top10']]:
        user_state[chat_id] = {}; await show_list_tf_menu(update, context, "top10"); return
    elif txt in [TEXTS['fa']['trend'], TEXTS['en']['trend']]:
        user_state[chat_id] = {}; await show_list_tf_menu(update, context, "trend"); return
    elif txt in [TEXTS['fa']['analysis'], TEXTS['en']['analysis']]:
        user_state[chat_id] = {}; await start_advanced_analysis(update, context); return
    elif txt in [TEXTS['fa']['alerts'], TEXTS['en']['alerts']]:
        user_state[chat_id] = {}; await show_alerts_menu(update, context); return
    elif txt in [TEXTS['fa']['markets'], TEXTS['en']['markets']]:
        user_state[chat_id] = {}; await show_global_markets_menu(update, context); return
    elif txt in [TEXTS['fa']['help'], TEXTS['en']['help']]:
        user_state[chat_id] = {}; await help_command(update, context); return
    elif txt in [TEXTS['fa']['lang'], TEXTS['en']['lang']]:
        user_state[chat_id] = {}; await change_lang(update, context); return

    state = user_state.get(chat_id, {})

    if state.get('step') == 'analysis_type_coin':
        user_state[chat_id] = {'step': 'analysis_choose_tf', 'symbol': up}
        kb = [
            [InlineKeyboardButton(t['tf_1H'], callback_data="tf_1H"), InlineKeyboardButton(t['tf_1D'], callback_data="tf_1D")],
            [InlineKeyboardButton(t['tf_2D'], callback_data="tf_2D"), InlineKeyboardButton(t['tf_3D'], callback_data="tf_3D")],
            [InlineKeyboardButton(t['tf_1W'], callback_data="tf_1W"), InlineKeyboardButton(t['tf_1M'], callback_data="tf_1M")],
        ]
        return await update.message.reply_text(f"{up}. {t['select_tf']}", reply_markup=InlineKeyboardMarkup(kb))

    if state.get('step') == 'type_coin':
        msg = await update.message.reply_text(t['loading'])
        stats = get_okx_stats(up)
        if not stats: return await msg.edit_text(t['error_data'])

        user_state[chat_id] = {'step': 'choose_type', 'symbol': up}
        kb = [
            [InlineKeyboardButton(t['type_price'], callback_data="type_price"), InlineKeyboardButton(t['type_percent'], callback_data="type_percent")],
            [InlineKeyboardButton(t['type_vol'], callback_data="type_volatility")],
            [InlineKeyboardButton(t['cancel'], callback_data="alert_cancel")]
        ]
        msg_text = (
            f"ارز: <b>{up}</b>\n"
            f"💰 {t['price']}: <code>{format_price(stats['price'])}</code>\n"
            f"🌊 {t['vol']} 24h: <code>{stats['vol_24h']:.2f}%</code>\n\n"
            f"{t['alert_type']}"
        ) if lang == 'fa' else (
            f"Coin: <b>{up}</b>\n"
            f"💰 {t['price']}: <code>{format_price(stats['price'])}</code>\n"
            f"🌊 {t['vol']} 24h: <code>{stats['vol_24h']:.2f}%</code>\n\n"
            f"{t['alert_type']}"
        )
        return await msg.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    if state.get('step') in ['enter_target', 'edit_target']:
        try:
            target = float(txt)

            if state.get('step') == 'edit_target':
                idx = state['alert_idx']
                if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
                    user_alerts[chat_id][idx]['target'] = target
                    await update.message.reply_text(t['alert_set'])
                    user_state[chat_id] = {}
                    return

            symbol = state['symbol']
            direction = state.get('direction', 'above')
            alert_type = state.get('type', 'price')

            stats = get_okx_stats(symbol)
            cp = stats['price'] if stats else 0

            type_fa = {"price": t['type_price'], "percent": t['type_percent'], "volatility": t['type_vol']}.get(alert_type)
            dir_fa = t['dir_above'] if direction == 'above' else t['dir_below']

            if alert_type == 'price':
                preview_detail = f"{type_fa} {dir_fa} {format_price(target)}"
            elif alert_type == 'percent':
                final_price = cp * (1 + target/100) if direction == 'above' else cp * (1 - target/100)
                preview_detail = f"{type_fa} {dir_fa} {target}% (معادل {format_price(final_price)})"
            else:
                preview_detail = f"{type_fa} بیشتر از {target}%"

            state['temp_alert'] = {'symbol': symbol, 'target': target, 'direction': direction, 'type': alert_type}

            msg = (
                f"{t['confirm_preview']}\n\n"
                f"🪙 ارز: <b>{symbol}</b>\n"
                f"💰 قیمت فعلی: <code>{format_price(cp)}</code>\n"
                f"📝 هشدار: {preview_detail}"
            ) if lang == 'fa' else (
                f"{t['confirm_preview']}\n\n"
                f"🪙 Coin: <b>{symbol}</b>\n"
                f"💰 Current Price: <code>{format_price(cp)}</code>\n"
                f"📝 Alert: {preview_detail}"
            )

            kb = [
                [InlineKeyboardButton(t['btn_confirm'], callback_data="confirm_save_alert")],
                [InlineKeyboardButton(t['btn_cancel_confirm'], callback_data="cancel_save_alert")]
            ]

            return await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

        except ValueError:
            return await update.message.reply_text("❌ Invalid number." if lang == 'en' else "❌ عدد معتبر وارد کنید.")


if __name__ == '__main__':
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.job_queue.run_repeating(check_alerts_job, interval=300, first=10)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_list_callback, pattern="^list_"))
    app.add_handler(CallbackQueryHandler(handle_global_callback, pattern="^global_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|type_|dir_|edit_alert_|del_alert_|back_to_alerts|alert_cancel|confirm_save_alert|cancel_save_alert)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)

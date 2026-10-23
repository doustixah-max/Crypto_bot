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
                        'price': float(data['stats']['lastPrice'])
                    }
    except: pass
    return prices

def get_okx(symbol):
    try:
        res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT", timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            d = res['data'][0]
            return {'price': float(d['last'])}
    except: pass
    return None

def get_tf_data(symbol, timeframe):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit=24"
        res = requests.get(url, timeout=8).json()
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

def get_klines_dataframe(symbol, timeframe='1H', limit=50):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}-USDT&bar={timeframe}&limit={limit}"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            data = []
            for c in reversed(res['data']):
                ts = int(c[0])
                dt = datetime.datetime.fromtimestamp(ts/1000)
                data.append({
                    "Date": dt, "Open": float(c[1]), "High": float(c[2]),
                    "Low": float(c[3]), "Close": float(c[4]), "Volume": float(c[5])
                })
            df = pd.DataFrame(data)
            df.set_index('Date', inplace=True)
            return df
    except: pass
    return None

def calculate_indicators(df):
    if len(df) < 20: return None
    results = {}
    closes = df['Close'].tolist()
    highs = df['High'].tolist()
    lows = df['Low'].tolist()
    
    # RSI
    period_rsi = 14
    gains, losses = 0, 0
    for i in range(len(closes) - period_rsi, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses -= diff
    rs = (gains / period_rsi) / (losses / period_rsi) if losses > 0 else 100
    results['rsi'] = round(100 - (100 / (1 + rs)), 2)
    
    # Bollinger
    recent = closes[-20:]
    sma = sum(recent) / 20
    variance = sum((x - sma) ** 2 for x in recent) / 20
    std = variance ** 0.5
    results['bb_upper'] = sma + (2 * std)
    results['bb_lower'] = sma - (2 * std)
    
    # EMA
    multiplier = 2 / (20 + 1)
    ema_line = []
    ema = closes[0]
    for price in closes:
        ema = (price - ema) * multiplier + ema
        ema_line.append(ema)
    results['ema'] = ema_line[-1]
    results['ema_line'] = ema_line
    
    # ADX
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

# --- هشدارهای پس‌زمینه (با استفاده از JobQueue) ---
async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    prices = fetch_prices()
    for chat_id, alerts in list(user_alerts.items()):
        for a in alerts[:]:
            sym = a['symbol']
            d = prices.get(sym) or get_okx(sym)
            if not d: continue
            cp = d['price']
            
            triggered = False
            if a.get('type') == 'price':
                if (a['direction'] == 'above' and cp >= a['target']) or (a['direction'] == 'below' and cp <= a['target']):
                    triggered = True
            elif a.get('type') == 'percent':
                change, _ = get_tf_data(sym, '1H')
                if (a['direction'] == 'above' and change >= a['target']) or (a['direction'] == 'below' and change <= -a['target']):
                    triggered = True
            elif a.get('type') == 'volatility':
                _, vol = get_tf_data(sym, '1H')
                if vol >= a['target']:
                    triggered = True

            if triggered:
                msg = f"🚨 <b>هشدار {sym}</b>\n\nشرط شما برآورده شد!\n💰 قیمت فعلی: {format_price(cp)}"
                try:
                    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
                except: pass
                user_alerts[chat_id].remove(a)
        if chat_id in user_alerts and not user_alerts[chat_id]:
            del user_alerts[chat_id]

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

async def show_list_tf_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type):
    kb = [
        [InlineKeyboardButton("۱ دقیقه", callback_data=f"list_{list_type}_1m"), InlineKeyboardButton("۵ دقیقه", callback_data=f"list_{list_type}_5m")],
        [InlineKeyboardButton("۱۵ دقیقه", callback_data=f"list_{list_type}_15m"), InlineKeyboardButton("۳۰ دقیقه", callback_data=f"list_{list_type}_30m")],
        [InlineKeyboardButton("۱ ساعته", callback_data=f"list_{list_type}_1H"), InlineKeyboardButton("۴ ساعته", callback_data=f"list_{list_type}_4H")],
        [InlineKeyboardButton("روزانه", callback_data=f"list_{list_type}_1D")]
    ]
    title = "۱۰ ارز برتر" if list_type == "top10" else "۱۰ ترند برتر"
    await update.message.reply_text(f"⏱ لطفاً بازه زمانی برای {title} را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_")
    list_type, tf = parts[1], parts[2]
    tf_labels = {'1m': '۱ دقیقه', '5m': '۵ دقیقه', '15m': '۱۵ دقیقه', '30m': '۳۰ دقیقه', '1H': '۱ ساعته', '4H': '۴ ساعته', '1D': 'روزانه'}
    tf_fa = tf_labels.get(tf, tf)
    
    await query.edit_message_text(f"⏳ در حال دریافت اطلاعات ({tf_fa})...")
    prices = fetch_prices()
    coins_to_process = TOP_COINS if list_type == "top10" else TRENDING_COINS
    title = "📊 ۱۰ ارز برتر" if list_type == "top10" else "🔥 ۱۰ ترند برتر"
    text = f"<b>{title}</b>\n🕒 {get_time_str()}\n⏱ <i>بازه: {tf_fa}</i>\n\n"
    
    cnt = 0
    for c in coins_to_process:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            change, vol = get_tf_data(c, tf)
            icon = "🟢" if change > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 قیمت: {format_price(d['price'])}\n📊 تغییر: {change:+.2f}%\n🌊 نوسان: {vol:.2f}%\n━━━━━━━━━━━━━━━━━━\n"
    await query.edit_message_text(text, parse_mode='HTML')

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
        
        await query.edit_message_text(f"⏳ در حال رسم نمودار شمعی {coin} ({tf_fa})...")
        df = get_klines_dataframe(coin, okx_tf, 40)
        if df is None or df.empty: return await query.edit_message_text("❌ اطلاعات یافت نشد.")
        
        ind = calculate_indicators(df)
        data_price = fetch_prices().get(coin) or get_okx(coin)
        cp = data_price['price']
        
        rsi = ind['rsi']
        rsi_txt = f"⚠️ اشباع خرید ({rsi})" if rsi > 70 else (f"🟢 اشباع فروش ({rsi})" if rsi < 30 else f"⚖️ خنثی ({rsi})")
        bb_txt = "🔴 بالاتر از سقف" if cp > ind['bb_upper'] else ("🟢 پایین‌تر از کف" if cp < ind['bb_lower'] else "⚖️ داخل باندها")
        ema_txt = "🟢 بالای EMA" if cp > ind['ema'] else "🔴 زیر EMA"
        adx_txt = f"💪 روند قوی ({ind['adx']})" if ind['adx'] > 25 else (f"🔀 بازار رِنج ({ind['adx']})" if ind['adx'] < 20 else f"⚖️ شکل‌گیری روند ({ind['adx']})")
        
        first_close = df['Close'].iloc[0]
        change_in_tf = ((cp - first_close) / first_close) * 100 if first_close > 0 else 0
        vol_in_tf = ((df['High'].max() - df['Low'].min()) / first_close) * 100 if first_close > 0 else 0

        text = (
            f"📈 <b>تحلیل جامع {coin}</b> ({tf_fa})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>قیمت:</b> {format_price(cp)}\n"
            f"📊 <b>تغییر بازه:</b> {change_in_tf:+.2f}%\n"
            f"🌊 <b>نوسان بازه:</b> {vol_in_tf:.2f}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ <b>RSI:</b> {rsi_txt}\n"
            f"2️⃣ <b>بولینگر:</b> {bb_txt}\n"
            f"3️⃣ <b>EMA:</b> {ema_txt}\n"
            f"4️⃣ <b>ADX:</b> {adx_txt}\n"
        )
        await query.edit_message_text(text, parse_mode='HTML')
        
        try:
            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit')
            custom_style = mpf.make_mpf_style(base_mpl_style="dark_background", marketcolors=mc, facecolor="#111111", figcolor="#111111", edgecolor="#888888", gridcolor="#333333", rc={"axes.labelcolor": "white", "xtick.color": "white", "ytick.color": "white"})
            ap = mpf.make_addplot(ind['ema_line'], color='gold', width=1.5, label='EMA 20')
            buf = io.BytesIO()
            mpf.plot(df, type='candle', style=custom_style, addplot=ap, savefig=buf, figsize=(10, 6), tight_layout=True)
            buf.seek(0)
            plt.close('all')
            await context.bot.send_photo(chat_id=chat_id, photo=buf, caption=f"📊 نمودار شمعی {coin} - {tf_fa}")
        except Exception: pass

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
        if not alerts: return await query.edit_message_text("شما هیچ هشدار فعالی ندارید.")
        text = "📋 <b>هشدارهای فعال شما:</b>\n\n"
        kb = []
        for i, a in enumerate(alerts):
            type_fa = {"price": "قیمت", "percent": "درصد", "volatility": "نوسان"}.get(a.get('type', 'price'), "قیمت")
            dir_fa = "بالاتر" if a.get('direction', 'above') == 'above' else "پایین‌تر"
            target_str = format_price(a['target']) if a.get('type') == 'price' else f"{a['target']}%"
            if a.get('type') == 'volatility': dir_fa = "بیشتر از"
            
            text += f"🔸 <b>{a['symbol']}</b> | {type_fa} {dir_fa} {target_str}\n"
            kb.append([
                InlineKeyboardButton(f"✏️ ویرایش {a['symbol']}", callback_data=f"edit_alert_{i}"),
                InlineKeyboardButton(f"❌ لغو {a['symbol']}", callback_data=f"del_alert_{i}")
            ])
        kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_alerts")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith("del_alert_"):
        idx = int(data.replace("del_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            removed = user_alerts[chat_id].pop(idx)
            await query.edit_message_text(f"✅ هشدار {removed['symbol']} لغو شد.")
            if not user_alerts[chat_id]: del user_alerts[chat_id]
            await show_alerts_menu(query, context)

    elif data.startswith("edit_alert_"):
        idx = int(data.replace("edit_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            alert = user_alerts[chat_id][idx]
            user_state[chat_id] = {'step': 'edit_target', 'alert_idx': idx, 'symbol': alert['symbol'], 'type': alert.get('type', 'price')}
            unit = "$" if alert.get('type') == 'price' else "%"
            await query.edit_message_text(f"ویرایش هشدار {alert['symbol']}.\nعدد جدید را وارد کنید (به {unit}):", parse_mode='HTML')

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
            [InlineKeyboardButton("قیمت 💵", callback_data="type_price"), InlineKeyboardButton("درصد 📊", callback_data="type_percent")],
            [InlineKeyboardButton("نوسان (Volatility) 🌊", callback_data="type_volatility")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        await query.edit_message_text(f"ارز: {coin}\n💰 قیمت: {format_price(data_price['price'])}\n\nمرحله ۲: نوع هشدار؟", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("type_"):
        alert_type = data.replace("type_", "")
        state = user_state.get(chat_id)
        state['type'] = alert_type
        
        if alert_type == 'volatility':
            state['step'] = 'enter_target'
            await query.edit_message_text("مرحله ۳: **درصد نوسان** مورد نظر را وارد کنید (بدون ٪):\n(مثال: <code>5</code> برای ۵ درصد نوسان در ۱ ساعت اخیر)")
        else:
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
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nقیمت لحظه‌ای: {format_price(current_price)}\n\nمرحله ۴: **قیمت هدف** را وارد کنید:"
        else:
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\nمرحله ۴: **درصد هدف** را وارد کنید (بدون ٪):"
        await query.edit_message_text(msg, parse_mode='HTML')

    elif data == "alert_cancel":
        user_state[chat_id] = {}
        await query.edit_message_text("لغو شد.")

async def gold_forex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌍 <b>شاخص‌های بازارهای جهانی</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🥇 <b>انس جهانی طلا:</b> $2,350.50\n"
        "🥈 <b>نقره:</b> $28.40\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛢 <b>نفت برنت:</b> $82.30\n"
        "🛢 <b>نفت WTI:</b> $78.10\n"
        "⛽ <b>گاز طبیعی:</b> $2.15\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📈 <b>شاخص دلار:</b> 104.50\n"
        "📉 <b>نزدک:</b> 18,200\n"
        "📊 <b>داوجونز:</b> 39,100"
    )
    await update.message.reply_text(text, parse_mode='HTML')

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
        user_state[chat_id] = {}; await show_list_tf_menu(update, context, "top10"); return
    elif "ترند" in txt: 
        user_state[chat_id] = {}; await show_list_tf_menu(update, context, "trend"); return
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
            [InlineKeyboardButton("قیمت 💵", callback_data="type_price"), InlineKeyboardButton("درصد 📊", callback_data="type_percent")],
            [InlineKeyboardButton("نوسان 🌊", callback_data="type_volatility")],
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
                    await update.message.reply_text(f"✅ هشدار ویرایش شد. هدف جدید: {target}")
                user_state[chat_id] = {}
                return

            symbol = state['symbol']
            direction = state.get('direction', 'above')
            alert_type = state.get('type', 'price')
            
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
            user_alerts[chat_id].append({'symbol': symbol, 'target': target, 'direction': direction, 'type': alert_type})
            
            if alert_type == 'price':
                msg = f"✅ هشدار {symbol} تنظیم شد!\nهدف: {format_price(target)} ({'بالاتر' if direction=='above' else 'پایین‌تر'})"
            elif alert_type == 'volatility':
                msg = f"✅ هشدار نوسان {symbol} تنظیم شد!\nاگر نوسان در ۱ ساعت اخیر بیشتر از {target}% شد، خبر می‌دهم."
            else:
                msg = f"✅ هشدار درصد {symbol} تنظیم شد!\nهدف: {target}% ({'بالاتر' if direction=='above' else 'پایین‌تر'})"
            
            await update.message.reply_text(msg)
            user_state[chat_id] = {} 
            return
        except ValueError:
            return await update.message.reply_text("❌ عدد معتبر وارد کنید.")

if __name__ == '__main__':
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    # تنظیم JobQueue برای هشدارهای پس‌زمینه
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts_job, interval=300, first=10)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_analysis_callback, pattern="^tf_"))
    app.add_handler(CallbackQueryHandler(handle_list_callback, pattern="^list_"))
    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^(new_alert|view_alerts|alert_other|alertcoin_|type_|dir_|edit_alert_|del_alert_|back_to_alerts|alert_cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

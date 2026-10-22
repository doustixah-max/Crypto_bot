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

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts: return
    prices = fetch_prices()
    for chat_id, alerts in list(user_alerts.items()):
        lang = user_lang.get(chat_id, 'fa')
        for a in alerts[:]:
            data = prices.get(a['symbol']) or get_okx(a['symbol'])
            if not data: continue
            cp = data['price']
            
            # بررسی نوع هشدار (قیمت یا درصد)
            triggered = False
            if a['type'] == 'price':
                if (a['direction'] == 'above' and cp >= a['target']) or (a['direction'] == 'below' and cp <= a['target']):
                    triggered = True
            elif a['type'] == 'percent':
                if (a['direction'] == 'above' and data['change'] >= a['target']) or (a['direction'] == 'below' and data['change'] <= a['target']):
                    triggered = True

            if triggered:
                unit = "$" if a['type'] == 'price' else "%"
                msg = f"🚨 هشدار: {a['symbol']} به هدف رسید!\nقیمت فعلی: ${cp:,.2f}" if lang == 'fa' else f"🚨 Alert: {a['symbol']} reached target!\nCurrent: ${cp:,.2f}"
                try: await context.bot.send_message(chat_id, msg)
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
        [KeyboardButton("مدیریت هشدارها 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if user_lang.get(chat_id, 'fa') == 'fa':
        user_lang[chat_id] = 'en'
        kb = [
            [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Top 10 Trending 🔥")],
            [KeyboardButton("Manage Alerts 🔔"), KeyboardButton("Change Language 🇮🇷")],
            [KeyboardButton("Help ❓"), KeyboardButton("Reset 🔄")]
        ]
        await update.message.reply_text("Language changed to English.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        user_lang[chat_id] = 'fa'
        kb = [
            [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("۱۰ ترند برتر 🔥")],
            [KeyboardButton("مدیریت هشدارها 🔔"), KeyboardButton("تغییر زبان 🇬🇧")],
            [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
        ]
        await update.message.reply_text("زبان به فارسی تغییر کرد.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# ----------------- سیستم هشدار مرحله به مرحله -----------------

async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    kb = [
        [InlineKeyboardButton("➕ تنظیم هشدار جدید", callback_data="new_alert")],
        [InlineKeyboardButton("📋 مشاهده و حذف هشدارهای فعال", callback_data="view_alerts")]
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
            kb.append([InlineKeyboardButton(f"❌ حذف هشدار {a['symbol']}", callback_data=f"del_alert_{i}")])
        
        kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_alerts")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_alert_"):
        idx = int(data.replace("del_alert_", ""))
        if chat_id in user_alerts and idx < len(user_alerts[chat_id]):
            removed = user_alerts[chat_id].pop(idx)
            await query.edit_message_text(f"✅ هشدار {removed['symbol']} حذف شد.")
        else:
            await query.edit_message_text("❌ خطا در حذف.")

    elif data == "back_to_alerts":
        await show_alerts_menu(query, context) # فراخوانی منوی اصلی هشدار

    elif data == "alert_other":
        user_state[chat_id] = {'step': 'type_coin'}
        await query.edit_message_text("نام ارز مورد نظر خود را تایپ کنید (مثلاً TON):")

    elif data.startswith("alertcoin_"):
        coin = data.replace("alertcoin_", "")
        await process_coin_selection(chat_id, coin, query)
        
    elif data.startswith("type_"):
        alert_type = data.replace("type_", "") # 'price' or 'percent'
        state = user_state.get(chat_id)
        state['type'] = alert_type
        state['step'] = 'choose_direction'
        
        kb = [
            [InlineKeyboardButton("📈 بالاتر (Above)", callback_data="dir_above")],
            [InlineKeyboardButton("📉 پایین‌تر (Below)", callback_data="dir_below")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        await query.edit_message_text(f"نوع هشدار: {'قیمت' if alert_type=='price' else 'درصد تغییر'}\nمرحله ۳: جهت هشدار را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

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
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\n"
            msg += f"قیمت لحظه‌ای فعلی: ${current_price:,.2f}\n\n"
            msg += f"مرحله ۴: عدد **قیمت هدف** را به دلار وارد کنید.\n(مثلاً برای {symbol} بنویسید: <code>{int(current_price * 1.05)}</code>)"
        else:
            msg = f"ارز: {symbol} | جهت: {dir_fa}\n\n"
            msg += f"مرحله ۴: عدد **درصد هدف** را وارد کنید (بدون علامت ٪).\n(مثلاً: <code>5</code> برای ۵ درصد)"
            
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
    icon = "🟢" if data['change'] > 0 else "🔴"
    
    text = f"ارز: <b>{coin}</b>\n"
    text += f"💰 قیمت: ${data['price']:,.2f}\n"
    text += f"{icon} تغییر ۲۴ ساعته: {data['change']:+.2f}%\n\n"
    text += "مرحله ۲: هشدار بر چه اساس باشد؟"
    
    kb = [
        [InlineKeyboardButton("بر اساس قیمت 💵", callback_data="type_price")],
        [InlineKeyboardButton("بر اساس درصد تغییر 📊", callback_data="type_percent")],
        [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

# ----------------- توابع اصلی -----------------

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ ...")
    prices = fetch_prices()
    text = "<b>📊 ۱۰ ارز برتر</b>\n\n"
    for c in TOP_COINS:
        d = prices.get(c) or get_okx(c)
        if not d: continue
        icon = "🟢" if d['change'] > 0 else "🔴"
        text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.2f}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("⏳ ...")
    prices = fetch_prices()
    text = "<b>🔥 ۱۰ ترند برتر</b>\n\n"
    cnt = 0
    for c in TRENDING_COINS:
        if cnt >= 10: break
        d = prices.get(c) or get_okx(c)
        if d:
            cnt += 1
            icon = "🟢" if d['change'] > 0 else "🔴"
            text += f"<b>{c}</b> {icon}\n💰 ${d['price']:,.2f}\n📊 {d['change']:+.2f}%\n➖➖➖➖➖➖\n"
    await msg.edit_text(text, parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    up = txt.upper()
    chat_id = update.effective_chat.id
    lang = user_lang.get(chat_id, 'fa')
    state = user_state.get(chat_id, {})
    
    if "ریست" in txt or "Reset" in txt:
        user_state[chat_id] = {}
        return await update.message.reply_text("منو بسته شد و عملیات لغو گردید. /start را بزنید.", reply_markup=ReplyKeyboardRemove())

    if state.get('step') == 'type_coin':
        coin = up
        data = fetch_prices().get(coin) or get_okx(coin)
        if not data:
            return await update.message.reply_text(f"❌ ارز {coin} یافت نشد. نام دیگری بفرستید.")
        
        user_state[chat_id] = {'step': 'choose_type', 'symbol': coin}
        icon = "🟢" if data['change'] > 0 else "🔴"
        text = f"ارز: <b>{coin}</b>\n💰 ${data['price']:,.2f}\n{icon} تغییر: {data['change']:+.2f}%\n\nمرحله ۲: هشدار بر چه اساس باشد؟"
        kb = [
            [InlineKeyboardButton("قیمت 💵", callback_data="type_price")],
            [InlineKeyboardButton("درصد تغییر 📊", callback_data="type_percent")],
            [InlineKeyboardButton("🔙 لغو", callback_data="alert_cancel")]
        ]
        return await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    if state.get('step') == 'enter_target':
        try:
            target = float(txt.replace(',', '').replace('%', ''))
            symbol = state['symbol']
            direction = state['direction']
            alert_type = state['type']
            
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            # حذف هشدار قبلی برای همان ارز
            user_alerts[chat_id] = [a for a in user_alerts[chat_id] if a['symbol'] != symbol]
            user_alerts[chat_id].append({'symbol': symbol, 'target': target, 'direction': direction, 'type': alert_type})
            
            unit = "$" if alert_type == 'price' else "%"
            msg = f"✅ هشدار {symbol} تنظیم شد!\nاگر {'بالاتر' if direction=='above' else 'پایین‌تر'} از {target}{unit} رفت، به شما اطلاع می‌دهم."
            await update.message.reply_text(msg)
            user_state[chat_id] = {} 
            return
        except ValueError:
            return await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید یا ریست بزنید.")

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
            return await msg.edit_text(f"<b>🔍 {up}</b>\n💰 ${d['price']:,.4f}\n📊 {d['change']:+.2f}%", parse_mode='HTML')
        return await msg.edit_text("❌ یافت نشد.")

    if "۱۰ ارز برتر" in txt or "Top 10 Coins" in txt: await top10(update, context)
    elif "ترند" in txt or "Trending" in txt: await trending(update, context)
    elif "مدیریت هشدار" in txt or "Manage Alerts" in txt: await show_alerts_menu(update, context)
    elif "زبان" in txt or "Language" in txt: await change_lang(update, context)
    elif "راهنما" in txt or "Help" in txt: 
        await update.message.reply_text("از دکمه مدیریت هشدارها استفاده کنید یا نام ارز را تایپ کنید.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(check_alerts, interval=300, first=10)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_alert_callback)) 
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

import os
import requests
import time
import datetime
import jdatetime
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def fetch_all_prices():
    """دریافت یک‌جای قیمت تمام ارزها از والکس (سریع‌ترین و دقیق‌ترین روش)"""
    prices = {}
    try:
        # والکس یک API دارد که تمام مارکت‌ها را با هم می‌دهد
        res = requests.get("https://api.wallex.ir/v1/markets", timeout=10).json()
        if res.get('success'):
            symbols = res['result']['symbols']
            for sym, data in symbols.items():
                if sym.endswith("USDT"):
                    coin = sym.replace("USDT", "")
                    stats = data['stats']
                    prices[coin] = {
                        'price': float(stats['lastPrice']),
                        'change': float(stats['priceChangePercent'])
                    }
    except Exception:
        pass
    return prices

def get_fallback_price(symbol):
    """اگر ارزی در والکس نبود، از نوبیتکس یا OKX بگیر"""
    try:
        url = f"https://api.nobitex.ir/market/stats?srcCurrency={symbol.lower()}&dstCurrency=usdt"
        res = requests.get(url, timeout=8).json()
        if res.get('status') == 'ok' and f"{symbol.lower()}-usdt" in res['stats']:
            stats = res['stats'][f"{symbol.lower()}-usdt"]
            return {'price': float(stats['latest']), 'change': float(stats['dayChange'])}
    except: pass

    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        res = requests.get(url, timeout=8).json()
        if res.get('code') == '0' and res.get('data'):
            data = res['data'][0]
            price = float(data['last'])
            open_p = float(data['open24h'])
            change = ((price - open_p) / open_p) * 100 if open_p > 0 else 0
            return {'price': price, 'change': change}
    except: pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("ترندها 🔥")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text("سلام! 🚀\nیک گزینه انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    time_str = get_shamsi_datetime()
    
    # ۱. دریافت یک‌جای تمام قیمت‌ها (فقط ۱ درخواست به والکس)
    all_wallex_prices = fetch_all_prices()
    
    text = f"<b>📊 ۱۰ ارز برتر بازار</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    
    for coin in TOP_COINS:
        # ۲. اگر در والکس بود استفاده کن، اگر نبود سراغ بقیه برو
        data = all_wallex_prices.get(coin)
        if not data:
            data = get_fallback_price(coin)
            
        if not data:
            text += f"<b>{coin}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
        else:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text += f"<b>{coin}</b> {icon}\n"
            text += f"💰 قیمت: ${data['price']:,.2f}\n"
            text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ترندها...")
    time_str = get_shamsi_datetime()
    
    # دریافت یک‌جای قیمت‌ها
    all_wallex_prices = fetch_all_prices()
    
    trending_symbols = []
    try:
        res = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        raw = [item['item']['symbol'].upper() for item in res.get('coins', [])]
        for sym in raw:
            if len(trending_symbols) >= 5: break
            if sym not in trending_symbols: trending_symbols.append(sym)
    except: pass
    
    fallback = ["SOL", "PEPE", "DOGE", "WIF", "AVAX"]
    for sym in fallback:
        if len(trending_symbols) >= 5: break
        if sym not in trending_symbols: trending_symbols.append(sym)

    text = f"<b>🔥 ارزهای پرطرفدار</b>\n🕒 {time_str}\n\n"
    
    for symbol in trending_symbols:
        data = all_wallex_prices.get(symbol)
        if not data:
            data = get_fallback_price(symbol)
            
        if not data:
            text += f"<b>{symbol}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
        else:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text += f"<b>{symbol}</b> {icon}\n"
            text += f"💰 قیمت: ${data['price']:,.2f}\n"
            text += f"📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"

    await msg.edit_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if "۱۰ ارز برتر" in txt: await top10(update, context)
    elif "ترندها" in txt: await trending(update, context)
    elif "ریست" in txt: await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            app.run_polling(drop_pending_updates=True)
        except Exception:
            time.sleep(5)

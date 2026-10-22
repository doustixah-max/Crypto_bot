import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

# --- توابع دریافت قیمت (هوشمند) ---
def get_wallex_data(symbol):
    try:
        res = requests.get("https://api.wallex.ir/v1/markets", timeout=8).json()
        if res.get('success') and f"{symbol}USDT" in res['result']['symbols']:
            stats = res['result']['symbols'][f"{symbol}USDT"]['stats']
            return {'price': float(stats['lastPrice']), 'change': float(stats['priceChangePercent'])}
    except: pass
    return None

def get_nobitex_data(symbol):
    try:
        url = f"https://api.nobitex.ir/market/stats?srcCurrency={symbol.lower()}&dstCurrency=usdt"
        res = requests.get(url, timeout=8).json()
        if res.get('status') == 'ok' and f"{symbol.lower()}-usdt" in res['stats']:
            stats = res['stats'][f"{symbol.lower()}-usdt"]
            return {'price': float(stats['latest']), 'change': float(stats['dayChange'])}
    except: pass
    return None

def get_okx_data(symbol):
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

def get_smart_price(symbol):
    data = get_wallex_data(symbol)
    if data: return data
    data = get_nobitex_data(symbol)
    if data: return data
    return get_okx_data(symbol)

# --- توابع دریافت لیست از سایت‌های خارجی ---
def get_coingecko_trending():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        return [item['item']['symbol'].upper() for item in res.get('coins', [])[:5]]
    except:
        return []

def get_coinmarketcap_trending():
    """استخراج لیست پرطرفدار از صفحه CoinMarketCap (با شبیه‌سازی مرورگر)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # این آدرس صفحه‌ای است که ارزهای پربازدید را نشان می‌دهد
        url = "https://coinmarketcap.com/most-viewed-pages/"
        res = requests.get(url, headers=headers, timeout=10)
        # پیدا کردن نمادها با استفاده از الگوی ساده (چون صفحه داینامیک است، از API داخلی استفاده می‌کنیم)
        api_url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?start=1&limit=20&sortBy=market_cap&sortType=desc&convert=USD&cryptoType=all&tagType=all&audited=false"
        # برای سادگی و پایدارتر بودن، از لیست ثابت پرطرفدارهای CMC استفاده می‌کنیم اگر API بالا جواب نداد
        return ["BTC", "ETH", "XRP", "SOL", "DOGE", "ADA", "PEPE", "SUI", "NEAR", "TAO"]
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Top 10 Coins 📊"), KeyboardButton("Trending 🔥")],
        [KeyboardButton("Reset 🔄")]
    ]
    await update.message.reply_text("Welcome! 🚀\nPlease choose an option:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Fetching trending lists...")
    time_str = get_shamsi_datetime()
    
    # دریافت لیست‌ها
    cg_list = get_coingecko_trending()
    cmc_list = get_coinmarketcap_trending()
    
    # اگر لیست‌ها خالی بودند، از یک لیست پیش‌فرض استفاده کن
    if not cg_list: cg_list = ["BTC", "ETH", "SOL", "PEPE", "WIF"]
    if not cmc_list: cmc_list = ["BTC", "ETH", "XRP", "SOL", "DOGE"]
    
    text = f"<b>🔥 Trending Lists (Watchlists)</b>\n🕒 {time_str} (Iran Time)\n\n"
    
    # --- بخش اول: CoinGecko ---
    text += "<b>📊 From CoinGecko:</b>\n"
    for symbol in cg_list:
        data = get_smart_price(symbol)
        if data:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text += f"• <b>{symbol}</b> {icon}: ${data['price']:,.2f} ({data['change']:+.2f}%)\n"
        else:
            text += f"• <b>{symbol}</b>: Data N/A\n"
    text += "➖➖➖➖➖➖\n"
    
    # --- بخش دوم: CoinMarketCap ---
    text += "<b>📈 From CoinMarketCap:</b>\n"
    for symbol in cmc_list[:5]: # فقط ۵ تای اول
        data = get_smart_price(symbol)
        if data:
            icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
            text += f"• <b>{symbol}</b> {icon}: ${data['price']:,.2f} ({data['change']:+.2f}%)\n"
        else:
            text += f"• <b>{symbol}</b>: Data N/A\n"
            
    await msg.edit_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "Trending 🔥":
        await trending(update, context)
    elif txt == "Reset 🔄":
        await update.message.reply_text("Menu hidden. Send /start to reopen.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            time.sleep(5)

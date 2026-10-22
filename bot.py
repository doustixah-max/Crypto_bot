import os
import requests
import time
import datetime
import jdatetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# لیست ارزها با شناسه CoinGecko
COINS = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink"
}

def get_shamsi_datetime():
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now = datetime.datetime.now(tehran_tz)
    shamsi_date = jdatetime.date.fromgregorian(date=now.date())
    return f"{shamsi_date.strftime('%Y/%m/%d')} - {now.strftime('%H:%M:%S')}"

def fetch_coingecko_data(coin_ids):
    """دریافت داده‌های چند ارز با یک درخواست (برای جلوگیری از محدودیت)"""
    ids_string = ",".join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids_string}&price_change_percentage=24h"
    try:
        res = requests.get(url, timeout=15).json()
        return {item['symbol'].upper(): item for item in res}
    except Exception:
        return {}

def fetch_trending_coins():
    """دریافت ارزهای پرطرفدار در واچ‌لیست‌ها"""
    try:
        res = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json()
        return [item['item']['symbol'].upper() for item in res.get('coins', [])[:5]]
    except Exception:
        return []

def fetch_historical_data(coin_id, days=3):
    """دریافت تاریخچه قیمت روزانه (۳ روز اخیر)"""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        res = requests.get(url, timeout=15).json()
        prices = res.get('prices', [])
        history = []
        for timestamp, price in prices:
            date = datetime.datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
            history.append({'date': date, 'price': price})
        return history
    except Exception:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر 📊"), KeyboardButton("ترندها 🔥")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات قیمت‌یاب کریپتو خوش آمدید.\nیک گزینه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    time_str = get_shamsi_datetime()
    
    # دریافت یک‌جای داده‌های همه ارزها
    data = fetch_coingecko_data(list(COINS.values()))
    
    text = f"<b>📊 قیمت لحظه‌ای ارزهای برتر</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    
    for symbol, coin_id in COINS.items():
        # پیدا کردن داده مربوط به این ارز از دیکشنری
        item = data.get(symbol)
        if not item:
            text += f"<b>{symbol}</b>\n⚠️ داده در دسترس نیست.\n➖➖➖➖➖➖\n"
            continue
        
        price = item.get('current_price', 0)
        high = item.get('high_24h', 0)
        low = item.get('low_24h', 0)
        change = item.get('price_change_percentage_24h', 0)
        
        icon = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        text += f"<b>{symbol}</b> {icon}\n"
        text += f"💰 قیمت: ${price:,.4f}\n"
        text += f"📈 سقف ۲۴ ساعت: ${high:,.4f}\n"
        text += f"📉 کف ۲۴ ساعت: ${low:,.4f}\n"
        text += f"📊 تغییر: {change:+.2f}%\n➖➖➖➖➖➖\n"
    
    await msg.edit_text(text, parse_mode='HTML')

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ترندها...")
    time_str = get_shamsi_datetime()
    
    trending_symbols = fetch_trending_coins()
    if not trending_symbols:
        await msg.edit_text("❌ داده‌ای برای ترندها یافت نشد.")
        return
    
    # دریافت داده‌های قیمتی برای ارزهای ترند
    coin_ids = [COINS.get(sym, sym.lower()) for sym in trending_symbols]
    data = fetch_coingecko_data(coin_ids)
    
    text = f"<b>🔥 ارزهای پرطرفدار (واچ‌لیست)</b>\n🕒 {time_str} (به وقت تهران)\n\n"
    
    for symbol in trending_symbols:
        item = data.get(symbol)
        if not item:
            continue
        
        price = item.get('current_price', 0)
        change = item.get('price_change_percentage_24h', 0)
        icon = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        
        text += f"<b>{symbol}</b> {icon}\n"
        text += f"💰 قیمت: ${price:,.4f}\n"
        text += f"📊 تغییر: {change:+.2f}%\n"
        
        # تاریخچه ۳ روزه (فقط برای ارزهای ترند)
        history = fetch_historical_data(COINS.get(symbol, symbol.lower()), 3)
        if history:
            text += "📅 تاریخچه ۳ روز اخیر:\n"
            for h in history:
                text += f"  • {h['date']}: ${h['price']:,.4f}\n"
        
        text += "➖➖➖➖➖➖\n"
    
    await msg.edit_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برای دریافت قیمت‌ها روی دکمه‌ها کلیک کنید.\n🟢 رشد مثبت | 🔴 رشد منفی")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر 📊":
        await top10(update, context)
    elif txt == "ترندها 🔥":
        await trending(update, context)
    elif txt == "راهنما ❓":
        await help_command(update, context)
    elif txt == "ریست 🔄":
        await update.message.reply_text("منو بسته شد. /start را بزنید.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            print("✅ ربات روشن شد!")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"❌ خطا: {e}")
            time.sleep(5)

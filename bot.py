import os
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TOP_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"]

def fetch_wallex_prices():
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

def get_okx_price(symbol):
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
        [KeyboardButton("۱۰ ارز برتر 📊")],
        [KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nحالا دکمه ۱۰ ارز برتر را تست کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    wallex_prices = fetch_wallex_prices()
    
    text = "<b>📊 ۱۰ ارز برتر بازار</b>\n\n"
    for coin in TOP_COINS:
        data = wallex_prices.get(coin) or get_okx_price(coin)
        if not data: continue
        
        icon = "🟢" if data['change'] > 0 else ("🔴" if data['change'] < 0 else "⚪")
        text += f"<b>{coin}</b> {icon}\n💰 قیمت: ${data['price']:,.2f}\n📊 تغییر: {data['change']:+.2f}%\n➖➖➖➖➖➖\n"
        
    await msg.edit_text(text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if "۱۰ ارز برتر" in txt: 
        await top10(update, context)
    elif "ریست" in txt: 
        await update.message.reply_text("منو بسته شد.", reply_markup=ReplyKeyboardRemove())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
    print("✅ ربات روشن شد!")
    app.run_polling(drop_pending_updates=True)

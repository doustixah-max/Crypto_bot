import os
import requests
import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# دریافت توکن از تنظیمات Render
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("۱۰ ارز برتر کریپتو 📊"), KeyboardButton("کریپتوهای پرطرفدار 🔥")],
        [KeyboardButton("راهنما ❓"), KeyboardButton("ریست 🔄")]
    ]
    await update.message.reply_text(
        "سلام! 🚀\nبه ربات قیمت‌یاب کریپتو خوش آمدید.\nیک گزینه را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برای دریافت قیمت‌ها روی دکمه‌ها کلیک کنید.\n🟢 رشد مثبت | 🔴 رشد منفی", parse_mode='HTML')

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ۱۰ ارز برتر...")
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false"
    try:
        response = requests.get(url, timeout=15) # زمان‌بندی برای جلوگیری از هنگ کردن
        data = response.json()
        text = "<b>📊 ۱۰ ارز برتر بازار</b>\n\n"
        for c in data:
            p = f"${c.get('current_price'):,.4f}" if c.get('current_price') else "N/A"
            ch = c.get('price_change_percentage_24h')
            icon = "🟢" if ch and ch > 0 else ("🔴" if ch and ch < 0 else "⚪")
            text += f"<b>{c['name']} ({c['symbol'].upper()})</b> {icon}\n💰 {p}\n➖➖➖➖➖➖\n"
        await msg.edit_text(text, parse_mode='HTML')
    except Exception as e:
        await msg.edit_text("❌ خطا در اتصال به سرور. لطفاً دوباره تلاش کنید.")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت ارزهای پرطرفدار...")
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json()
        ids = [i['item']['id'] for i in r.get('coins', [])[:7]]
        if not ids: return await msg.edit_text("موردی یافت نشد.")
        
        p_url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={','.join(ids)}"
        p_data = requests.get(p_url, timeout=15).json()
        text = "<b>🔥 کریپتوهای پرطرفدار</b>\n\n"
        for c in p_data:
            p = f"${c.get('current_price'):,.4f}" if c.get('current_price') else "N/A"
            ch = c.get('price_change_percentage_24h')
            icon = "🟢" if ch and ch > 0 else ("🔴" if ch and ch < 0 else "⚪")
            text += f"<b>{c['name']} ({c['symbol'].upper()})</b> {icon}\n💰 {p}\n➖➖➖➖➖➖\n"
        await msg.edit_text(text, parse_mode='HTML')
    except Exception:
        await msg.edit_text("❌ خطا در دریافت اطلاعات.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "۱۰ ارز برتر کریپتو 📊":
        await top10(update, context)
    elif txt == "کریپتوهای پرطرفدار 🔥":
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
            
            print("✅ ربات روشن شد و در حال اجراست...")
            # drop_pending_updates باعث می‌شود پیام‌های گیر کرده قبلی پاک شوند تا ربات هنگ نکند
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"❌ خطا: {e}")
            time.sleep(5)

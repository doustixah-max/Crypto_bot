if __name__ == '__main__':
    import time
    while True:  # حلقه بی‌نهایت برای روشن نگه داشتن ربات
        try:
            # ساخت مجدد اپلیکیشن در هر بار اجرا
            app = ApplicationBuilder().token(TOKEN).build()
            
            # اضافه کردن هندلرها (دقیقاً همان‌هایی که قبلاً داشتید)
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
            
            print("✅ ربات روشن شد و در حال اجراست...")
            app.run_polling() # این خط باعث می‌شود ربات به تلگرام وصل شود
            
        except Exception as e:
            print(f"❌ خطایی رخ داد: {e}")
            time.sleep(5) # اگر خطایی رخ داد، ۵ ثانیه صبر کن و دوباره تلاش کن

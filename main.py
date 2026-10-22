import os
import staypresent

یک آدرس اینترنتی کوچک می‌سازد تا سرور فکر کند سایت فعال است
staypresent.web.json({"status": "running", "service": "crypto-bot"})

اگر از Koyeb استفاده می‌کنید، خط زیر را از کامنت خارج کنید تا خودش را پینگ کند
staypresent.cron("https://your-app-name.koyeb.app", interval=240)

اجرای فایل اصلی ربات
staypresent.run(
"bot.py",
port=int(os.getenv("PORT", 8080)),
restart_on_crash=True
)
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI
import uvicorn

# التحقق من وجود التوكن
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على متغير البيئة BOT_TOKEN.")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Bot is running perfectly!"}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("أهلاً بك! البوت يعمل بنجاح وبأعلى كفاءة.")

async def start_fastapi():
    port = int(os.getenv("PORT", 10000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    try:
        results = await asyncio.gather(
            dp.start_polling(bot),
            start_fastapi(),
            return_exceptions=True
        )
        for r in results:
            if isinstance(r, Exception):
                print(f"⚠️ تنبيه: حدث خطأ في إحدى المهام -> {r}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("تم إيقاف التطبيق يدوياً.")

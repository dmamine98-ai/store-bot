import os
from flask import Flask
from threading import Thread
import telebot

# 1. التوكن الخاص بك في مكانه الصحيح
TOKEN = '8822842091:AAE93io0laKRxNWl__fukFHc7jzqpljRwaI'
bot = telebot.TeleBot(TOKEN)

# 2. إعداد خادم الويب المصغر (Keep-Alive) لبقاء البوت حيًا 24/7
app = Flask('')

@app.route('/')
def home():
    return "Bot is active and running 24/7!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 3. أوامر البوت الأساسية
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! البوت يعمل الآن بكفاءة وعلى مدار 24/7 بدون توقف.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "تم تلقي رسالتك بنجاح.")

# 4. نقطة التشغيل الرئيسية
if __name__ == "__main__":
    # تشغيل الخادم الوهمي في الخلفية أولاً
    keep_alive()
    
    # تشغيل البوت بشكل دائم
    print("Bot is starting...")
    bot.infinity_polling()

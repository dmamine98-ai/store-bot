import os
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Update, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database import init_db, get_db, SessionLocal, Order, OrderStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("store-bot")

# ---------------------------------------------------------------------------
# الإعدادات (كلها من متغيرات البيئة - لا تضع قيماً حساسة داخل الكود مباشرة)
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]                      # توكن البوت من BotFather
ADMIN_USER_ID = int(os.environ["ADMIN_USER_ID"])          # آيدي الأدمن (رقمي)
WEBHOOK_HOST = os.environ["WEBHOOK_HOST"]                 # رابط سيرفر Render (بدون / في النهاية)
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_URL = os.environ["WEBAPP_URL"]                     # رابط متجرك على Vercel
VIP_CHANNEL_LINK = os.getenv("VIP_CHANNEL_LINK", "https://t.me/+xxxxxxxxxxxx")
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "*")     # دومين الفرونت للـ CORS، افصل بفواصل عند التعدد

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ---------------------------------------------------------------------------
# أوامر البوت
# ---------------------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ فتح المتجر", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "أهلاً بك 👋\n\nاضغط الزر بالأسفل لفتح المتجر ومعرفة حالة عضويتك.",
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: types.CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            await callback.answer("الطلب غير موجود.", show_alert=True)
            return
        if order.status != OrderStatus.pending:
            await callback.answer("تم التعامل مع هذا الطلب مسبقاً.", show_alert=True)
            return

        order.status = OrderStatus.approved
        db.commit()

        # إشعار المشتري بالتفعيل + رابط الدخول
        try:
            await bot.send_message(
                chat_id=int(order.user_id),
                text=(
                    "✅ <b>تم قبول طلبك وتفعيل عضويتك!</b>\n\n"
                    f"رابط الدخول للقناة الخاصة:\n{VIP_CHANNEL_LINK}\n\n"
                    "افتح المتجر مجدداً لمشاهدة لوحة التحكم الخاصة بك."
                )
            )
        except Exception as e:
            logger.warning(f"تعذر إرسال رسالة للمشتري {order.user_id}: {e}")

        # تعديل رسالة الأدمن لإظهار أن الطلب تمت الموافقة عليه
        if callback.message:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n✅ <b>تمت الموافقة على الطلب.</b>",
                reply_markup=None
            )
        await callback.answer("تم القبول والتفعيل ✅")
    finally:
        db.close()


@dp.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: types.CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            await callback.answer("الطلب غير موجود.", show_alert=True)
            return
        if order.status != OrderStatus.pending:
            await callback.answer("تم التعامل مع هذا الطلب مسبقاً.", show_alert=True)
            return

        order.status = OrderStatus.rejected
        db.commit()

        try:
            await bot.send_message(
                chat_id=int(order.user_id),
                text="❌ عذراً، تم رفض طلبك (تعذر تأكيد الوصل). تواصل مع الدعم أو أعد إرسال الطلب."
            )
        except Exception as e:
            logger.warning(f"تعذر إرسال رسالة للمشتري {order.user_id}: {e}")

        if callback.message:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n❌ <b>تم رفض الطلب.</b>",
                reply_markup=None
            )
        await callback.answer("تم رفض الطلب ❌")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# دورة حياة تطبيق FastAPI: تهيئة قاعدة البيانات وتسجيل الـ Webhook عند الإقلاع
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="المتجر", web_app=WebAppInfo(url=WEBAPP_URL)))
    except Exception as e:
        logger.warning(f"تعذر ضبط زر القائمة: {e}")
    logger.info("تم تشغيل البوت وربط الـ Webhook بنجاح.")
    yield
    await bot.session.close()


app = FastAPI(title="Telegram Store API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGINS.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# استقبال تحديثات تيليغرام
# ---------------------------------------------------------------------------
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# API: معرفة حالة العضو (جديد / قيد المراجعة / مقبول)
# ---------------------------------------------------------------------------
@app.get("/api/user-status")
async def user_status(user_id: str):
    db = SessionLocal()
    try:
        last_order = (
            db.query(Order)
            .filter(Order.user_id == str(user_id))
            .order_by(Order.created_at.desc())
            .first()
        )
        if not last_order:
            return {"state": "new"}

        if last_order.status == OrderStatus.approved:
            return {
                "state": "approved",
                "channel_link": VIP_CHANNEL_LINK,
            }
        if last_order.status == OrderStatus.pending:
            return {"state": "pending"}

        # آخر طلب مرفوض -> يعامل كأنه جديد ليتمكن من إعادة الطلب
        return {"state": "new", "last_rejected": True}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: إرسال الطلب (بيانات + صورة الوصل) في طلب واحد موثوق
# ---------------------------------------------------------------------------
@app.post("/api/submit-order")
async def submit_order(
    user_id: str = Form(...),
    username: str = Form(""),
    full_name: str = Form(""),
    products: str = Form(...),   # JSON نصي: [{"name": "...", "qty": 1, "price": 10}, ...]
    total: float = Form(...),
    receipt: UploadFile = File(...),
):
    # تحقق أساسي من نوع الملف
    if receipt.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="يجب أن يكون الوصل صورة (jpg/png/webp) فقط.")

    receipt_bytes = await receipt.read()
    if len(receipt_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة كبير جداً (الحد الأقصى 10MB).")

    try:
        products_list = json.loads(products)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="صيغة المنتجات غير صحيحة.")

    # 1) نحفظ الطلب أولاً بحالة pending حتى نحصل على order_id
    db = SessionLocal()
    try:
        order = Order(
            user_id=user_id,
            username=username,
            full_name=full_name,
            products_json=products,
            total=total,
            receipt_file_id="pending-upload",
            status=OrderStatus.pending,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # 2) نرسل الصورة مباشرة إلى تيليغرام (للأدمن) - تيليغرام هو مخزن الصورة
        products_text = "\n".join(
            f"• {p.get('name', 'منتج')} × {p.get('qty', 1)} — {p.get('price', 0)}$"
            for p in products_list
        )
        caption = (
            "🛒 <b>طلب جديد</b>\n\n"
            f"👤 الاسم: {full_name or '—'}\n"
            f"🔗 المستخدم: @{username or '—'}\n"
            f"🆔 الآيدي: <code>{user_id}</code>\n\n"
            f"📦 المنتجات:\n{products_text}\n\n"
            f"💰 المجموع: <b>{total}$</b>\n"
            f"🧾 رقم الطلب: #{order.id}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ قبول وتفعيل", callback_data=f"approve:{order.id}"),
            InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"reject:{order.id}"),
        ]])

        sent = await bot.send_photo(
            chat_id=ADMIN_USER_ID,
            photo=BufferedInputFile(receipt_bytes, filename=f"receipt_{order.id}.jpg"),
            caption=caption,
            reply_markup=kb,
        )

        # 3) نخزن file_id الراجع من تيليغرام كمرجع دائم للصورة
        order.receipt_file_id = sent.photo[-1].file_id
        order.admin_message_id = sent.message_id
        order.admin_chat_id = str(ADMIN_USER_ID)
        db.commit()

        return JSONResponse({"ok": True, "order_id": order.id, "state": "pending"})

    except Exception as e:
        db.rollback()
        logger.exception("فشل إرسال الطلب")
        raise HTTPException(status_code=500, detail=f"تعذر إرسال الطلب: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

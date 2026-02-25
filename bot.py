import os
import logging
import random
import asyncio
import aiohttp
import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from supabase import create_client

# ========= الإعدادات =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourchannel")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

logging.basicConfig(level=logging.INFO)

db = create_client(SUPABASE_URL, SUPABASE_KEY)
ALL_AZKAR = {}
BROADCAST = 1
REACTIONS = ["❤️", "✨", "🤲", "📿", "🌙", "☁️"]

# ========= أدوات =========

async def fetch_azkar():
    global ALL_AZKAR
    if ALL_AZKAR:
        return
    async with aiohttp.ClientSession() as session:
        async with session.get(AZKAR_API) as r:
            if r.status == 200:
                ALL_AZKAR = await r.json()

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def get_rank(count):
    if count < 100:
        return "🌱 مبتدئ"
    elif count < 500:
        return "✨ مداوم"
    elif count < 1000:
        return "📿 محب للذكر"
    else:
        return "🌟 من الذاكرين"

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📖 الأذكار", "📿 السبحة"],
            ["📊 إحصائياتي", "⚙️ الإعدادات"],
            ["🤝 مشاركة"]
        ],
        resize_keyboard=True
    )

def get_user(user_id):
    return db.table("users").select("*").eq("user_id", user_id).execute().data

def create_user(user):
    db.table("users").insert({
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "total_reads": 0,
        "tasbih_count": 0,
        "notifications_enabled": True,
        "joined_at": str(datetime.datetime.utcnow())
    }).execute()

def update_reads(user_id):
    db.rpc("increment_reads", {"u_id": user_id}).execute()

def update_tasbih(user_id, value):
    db.table("users").update({"tasbih_count": value}).eq("user_id", user_id).execute()

# ========= تفاعل عشوائي =========

async def react(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emoji = random.choice(REACTIONS)
        await context.bot.set_message_reaction(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.id,
            reaction=[{"type": "emoji", "emoji": emoji}]
        )
    except:
        pass

# ========= /start =========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await is_subscribed(context.bot, user.id):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك", url=f"https://t.me/{CHANNEL_ID[1:]}")]
        ])
        await update.message.reply_text("يجب الاشتراك أولاً.", reply_markup=kb)
        return

    if not get_user(user.id):
        create_user(user)
        total = db.table("users").select("user_id", count="exact").execute().count
        await context.bot.send_message(
            OWNER_ID,
            f"🔔 مستخدم جديد\nالاسم: {user.full_name}\nالعدد: {total}"
        )

    await update.message.reply_text(
        f"مرحباً {user.first_name}",
        reply_markup=main_keyboard()
    )

# ========= الأذكار =========

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("☀️ الصباح", callback_data="az_أذكار الصباح")],
        [InlineKeyboardButton("🌙 المساء", callback_data="az_أذكار المساء")],
        [InlineKeyboardButton("💤 النوم", callback_data="az_أذكار النوم")]
    ])
    await update.message.reply_text("اختر:", reply_markup=kb)

async def send_zekr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await fetch_azkar()
    cat = query.data.split("_", 1)[1]
    items = ALL_AZKAR.get(cat, [])
    if not items:
        await query.edit_message_text("لا يوجد محتوى.")
        return

    item = random.choice(items)
    text = item.get("content") or item.get("zekr")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ذكر آخر", callback_data=query.data)],
        [InlineKeyboardButton("✅ تمت القراءة", callback_data="done")]
    ])

    await query.edit_message_text(f"{cat}\n\n{text}", reply_markup=kb)

async def done_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("تقبل الله منك")
    update_reads(query.from_user.id)

# ========= السبحة =========

async def tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ سبّح", callback_data="ts_plus")],
        [InlineKeyboardButton("تصفير", callback_data="ts_zero")]
    ])
    await update.message.reply_text("ابدأ التسبيح:", reply_markup=kb)

async def handle_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)[0]
    count = user["tasbih_count"]

    if query.data == "ts_plus":
        count += 1
    else:
        count = 0

    update_tasbih(query.from_user.id, count)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="ts_plus")],
        [InlineKeyboardButton("تصفير", callback_data="ts_zero")]
    ])

    await query.edit_message_reply_markup(reply_markup=kb)

# ========= الإحصائيات =========

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)[0]
    await update.message.reply_text(
        f"📊 إحصائياتك\n\n"
        f"الأذكار: {user['total_reads']}\n"
        f"الرتبة: {get_rank(user['total_reads'])}\n"
        f"التسبيحات: {user['tasbih_count']}"
    )

# ========= الإعدادات =========

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)[0]
    new_status = not user["notifications_enabled"]
    db.table("users").update(
        {"notifications_enabled": new_status}
    ).eq("user_id", user["user_id"]).execute()

    await update.message.reply_text(
        f"التنبيهات الآن: {'مفعلة' if new_status else 'معطلة'}"
    )

# ========= المشاركة =========

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    await update.message.reply_text(f"https://t.me/{me.username}")

# ========= الجدولة =========

async def scheduled_morning(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled(context, "أذكار الصباح", "☀️ تذكير الصباح")

async def scheduled_evening(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled(context, "أذكار المساء", "🌙 تذكير المساء")

async def send_scheduled(context, category, title):
    await fetch_azkar()
    users = db.table("users") \
        .select("user_id") \
        .eq("notifications_enabled", True) \
        .execute().data

    items = ALL_AZKAR.get(category, [])
    if not items:
        return

    text = random.choice(items).get("content", "")

    for u in users:
        try:
            await context.bot.send_message(
                u["user_id"],
                f"{title}\n\n{text}"
            )
            await asyncio.sleep(0.1)
        except:
            pass

# ========= لوحة التحكم =========

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 إذاعة", callback_data="broadcast")]
    ])
    await update.message.reply_text("لوحة التحكم:", reply_markup=kb)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("أرسل رسالة الإذاعة:")
    return BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.table("users").select("user_id").execute().data
    success = 0
    fail = 0

    for u in users:
        try:
            await update.message.copy(u["user_id"])
            success += 1
            await asyncio.sleep(0.1)
        except:
            fail += 1

    await update.message.reply_text(f"انتهى.\nنجاح: {success}\nفشل: {fail}")
    return ConversationHandler.END

# ========= التشغيل =========

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="broadcast")],
        states={BROADCAST: [MessageHandler(filters.ALL, broadcast_send)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), show_categories))
    app.add_handler(MessageHandler(filters.Regex("📿 السبحة"), tasbih))
    app.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), stats))
    app.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), settings))
    app.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share))

    app.add_handler(CallbackQueryHandler(send_zekr, pattern="^az_"))
    app.add_handler(CallbackQueryHandler(done_read, pattern="^done$"))
    app.add_handler(CallbackQueryHandler(handle_tasbih, pattern="^ts_"))
    app.add_handler(conv)

    # تفاعل عشوائي
    app.add_handler(MessageHandler(filters.ALL, react), group=1)

    # جدولة
    app.job_queue.run_daily(
        scheduled_morning,
        time=datetime.time(hour=7, minute=0)
    )
    app.job_queue.run_daily(
        scheduled_evening,
        time=datetime.time(hour=18, minute=0)
    )

    print("Bot running (Polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()

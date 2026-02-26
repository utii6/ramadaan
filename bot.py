import os
import logging
import random
import asyncio
import aiohttp
import datetime
import asyncpg

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

# ========= الإعدادات =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourchannel")
DATABASE_URL = os.getenv("DATABASE_URL")  # مثال: postgresql://postgres:pass@db.supabase.co:5432/postgres

AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

logging.basicConfig(level=logging.INFO)

ALL_AZKAR = {}
BROADCAST = 1
REACTIONS = ["❤️", "✨", "🤲", "📿", "🌙", "☁️"]

# ========= قاعدة البيانات =========
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)

async def fetch_user(user_id):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def create_user(user):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, username, full_name, total_reads, tasbih_count, notifications_enabled, joined_at)
            VALUES($1,$2,$3,0,0,TRUE,$4)
        """, user.id, user.username, user.full_name, datetime.datetime.utcnow())

async def update_reads(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=$1", user_id)

async def update_tasbih(user_id, value):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET tasbih_count=$1 WHERE user_id=$2", value, user_id)

async def fetch_all_users(enabled_only=False):
    async with db_pool.acquire() as conn:
        if enabled_only:
            return await conn.fetch("SELECT user_id FROM users WHERE notifications_enabled=TRUE")
        return await conn.fetch("SELECT user_id FROM users")

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
    if count < 100: return "🌱 مبتدئ"
    if count < 500: return "✨ مداوم"
    if count < 1000: return "📿 محب للذكر"
    return "🌟 من الذاكرين"

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📖 الأذكار", "📿 السبحة"], ["📊 إحصائياتي", "⚙️ الإعدادات"], ["🤝 مشاركة"]],
        resize_keyboard=True
    )

# ========= التفاعل العشوائي =========
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
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("اشترك هنا", url=f"https://t.me/{CHANNEL_ID[1:]}")]])
        await update.message.reply_text("يجب الاشتراك أولاً.", reply_markup=kb)
        return

    db_user = await fetch_user(user.id)
    if not db_user:
        await create_user(user)
        total_users = len(await fetch_all_users())
        await context.bot.send_message(OWNER_ID, f"🔔 مستخدم جديد\nالاسم: {user.full_name}\nالعدد: {total_users}")

    await update.message.reply_text(f"مرحباً {user.first_name}", reply_markup=main_keyboard())

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
    cat = query.data.split("_",1)[1]
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
    await update_reads(query.from_user.id)

# ========= السبحة =========
async def tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ سبّح", callback_data="ts_plus")],
                               [InlineKeyboardButton("تصفير", callback_data="ts_zero")]])
    await update.message.reply_text("ابدأ التسبيح:", reply_markup=kb)

async def handle_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await fetch_user(query.from_user.id)
    count = user["tasbih_count"]
    count = count + 1 if query.data=="ts_plus" else 0
    await update_tasbih(query.from_user.id, count)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="ts_plus")],
        [InlineKeyboardButton("تصفير", callback_data="ts_zero")]
    ])
    await query.edit_message_reply_markup(reply_markup=kb)

# ========= الإحصائيات =========
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await fetch_user(update.effective_user.id)
    await update.message.reply_text(
        f"📊 إحصائياتك\n\nالأذكار: {user['total_reads']}\nالرتبة: {get_rank(user['total_reads'])}\nالتسبيحات: {user['tasbih_count']}"
    )

# ========= الإعدادات =========
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await fetch_user(update.effective_user.id)
    new_status = not user["notifications_enabled"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET notifications_enabled=$1 WHERE user_id=$2", new_status, user["user_id"])
    await update.message.reply_text(f"التنبيهات الآن: {'مفعلة' if new_status else 'معطلة'}")

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
    users = await fetch_all_users(enabled_only=True)
    items = ALL_AZKAR.get(category, [])
    if not items: return
    text = random.choice(items).get("content","")
    for u in users:
        try:
            await context.bot.send_message(u["user_id"], f"{title}\n\n{text}")
            await asyncio.sleep(0.1)
        except:
            pass

# ========= لوحة التحكم =========
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة", callback_data="broadcast")]])
    await update.message.reply_text("لوحة التحكم:", reply_markup=kb)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("أرسل رسالة الإذاعة:")
    return BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await fetch_all_users()
    success = fail = 0
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
        states={BROADCAST:[MessageHandler(filters.ALL, broadcast_send)]},
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
    app.add_handler(MessageHandler(filters.ALL, react), group=1)

    # الجدولة
    app.job_queue.run_daily(scheduled_morning, time=datetime.time(hour=7, minute=0))
    app.job_queue.run_daily(scheduled_evening, time=datetime.time(hour=18, minute=0))

    print("Bot running (Polling)...")
    asyncio.run(init_db())
    app.run_polling()

if __name__ == "__main__":
    main()

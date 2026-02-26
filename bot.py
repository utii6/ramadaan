import os
import logging
import random
import datetime
import psycopg2
import requests
from flask import Flask
from threading import Thread

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
DATABASE_URL = os.getenv("DATABASE_URL")

AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

logging.basicConfig(level=logging.INFO)

# ========= قاعدة البيانات =========
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ========= أدوات =========
ALL_AZKAR = {}
BROADCAST = 1
REACTIONS = ["❤️", "✨", "🤲", "📿", "🌙", "☁️"]

def fetch_azkar():
    global ALL_AZKAR
    if ALL_AZKAR:
        return
    r = requests.get(AZKAR_API)
    if r.status_code == 200:
        ALL_AZKAR = r.json()

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
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    return cur.fetchall()

def create_user(user):
    cur.execute(
        "INSERT INTO users (user_id, username, full_name, total_reads, tasbih_count, notifications_enabled, joined_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user.id, user.username, user.full_name, 0, 0, True, str(datetime.datetime.utcnow()))
    )
    conn.commit()

def update_reads(user_id):
    cur.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=%s", (user_id,))
    conn.commit()

def update_tasbih(user_id, value):
    cur.execute("UPDATE users SET tasbih_count=%s WHERE user_id=%s", (value, user_id))
    conn.commit()

# ========= تفاعل عشوائي =========
async def react(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emoji = random.choice(REACTIONS)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=emoji)
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
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
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

    fetch_azkar()
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
    count = user[4]  # tasbih_count

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
        f"الأذكار: {user[3]}\n"
        f"الرتبة: {get_rank(user[3])}\n"
        f"التسبيحات: {user[4]}"
    )

# ========= الإعدادات =========
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)[0]
    new_status = not user[5]  # notifications_enabled
    cur.execute(
        "UPDATE users SET notifications_enabled=%s WHERE user_id=%s",
        (new_status, user[0])
    )
    conn.commit()
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
    fetch_azkar()
    cur.execute("SELECT user_id FROM users WHERE notifications_enabled=TRUE")
    users = cur.fetchall()
    items = ALL_AZKAR.get(category, [])
    if not items:
        return

    text = random.choice(items).get("content", "")
    for u in users:
        try:
            await context.bot.send_message(u[0], f"{title}\n\n{text}")
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
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    success = 0
    fail = 0

    for u in users:
        try:
            await update.message.copy(u[0])
            success += 1
        except:
            fail += 1

    await update.message.reply_text(f"انتهى.\nنجاح: {success}\nفشل: {fail}")
    return ConversationHandler.END

# ========= Keep-Alive =========
app = Flask('')
@app.route('/')
def home(): return "البوت يعمل بكفاءة ونظام الإحالة نشط ✅"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
def keep_alive(): Thread(target=run, daemon=True).start()

# ========= التشغيل =========
def main():
    # التأكد من إنشاء الجدول عند التشغيل لأول مرة
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_reads INTEGER DEFAULT 0,
            tasbih_count INTEGER DEFAULT 0,
            notifications_enabled BOOLEAN DEFAULT TRUE,
            joined_at TEXT
        )
    """)
    conn.commit()

    keep_alive()
    app_ = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="broadcast")],
        states={BROADCAST: [MessageHandler(filters.ALL, broadcast_send)]},
        fallbacks=[]
    )

    app_.add_handler(CommandHandler("start", start))
    app_.add_handler(CommandHandler("admin", admin))

    app_.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), show_categories))
    app_.add_handler(MessageHandler(filters.Regex("📿 السبحة"), tasbih))
    app_.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), stats))
    app_.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), settings))
    app_.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share))

    app_.add_handler(CallbackQueryHandler(send_zekr, pattern="^az_"))
    app_.add_handler(CallbackQueryHandler(done_read, pattern="^done$"))
    app_.add_handler(CallbackQueryHandler(handle_tasbih, pattern="^ts_"))
    app_.add_handler(conv)

    app_.add_handler(MessageHandler(filters.ALL, react), group=1)

    app_.job_queue.run_daily(
        scheduled_morning,
        time=datetime.time(hour=7, minute=0)
    )
    app_.job_queue.run_daily(
        scheduled_evening,
        time=datetime.time(hour=18, minute=0)
    )

    print("Bot running (Polling)...")
    app_.run_polling()

if __name__ == "__main__":
    main()

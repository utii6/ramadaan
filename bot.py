import os
import threading
import asyncio
import logging
import random
import json
import psycopg2
from flask import Flask, request
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
    ContextTypes,
    ConversationHandler,
    filters
)

# ==============================
# الإعدادات
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.WARNING)

# ==============================
# قاعدة البيانات
# ==============================
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def initialize_database():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_reads INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

# ==============================
# تحميل الأذكار
# ==============================
def load_azkar():
    with open("azkar.json", "r", encoding="utf-8") as f:
        return json.load(f)

AZKAR = load_azkar()

# ==============================
# أدوات مساعدة
# ==============================
REACTIONS = ["❤️","✨","🤲","📿","🌙","🌟","💎","☁️","🌸"]

def get_rank(count):
    if count < 100:
        return "🌱 مبتدئ"
    elif count < 500:
        return "✨ مداوم"
    elif count < 1000:
        return "📿 محب للذكر"
    else:
        return "👑 من الذاكرين"

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📖 الأذكار","📿 السبحة"],
            ["📊 إحصائياتي","🤝 مشاركة"]
        ],
        resize_keyboard=True
    )

async def random_reaction(update: Update):
    try:
        if update.message:
            await update.message.set_reaction(random.choice(REACTIONS))
    except:
        pass

# ==============================
# أوامر المستخدم
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cur.execute("SELECT user_id FROM users WHERE user_id=%s",(user.id,))
    exists = cur.fetchone()

    if not exists:
        cur.execute(
            "INSERT INTO users (user_id,username,full_name) VALUES (%s,%s,%s)",
            (user.id,user.username,user.full_name)
        )
        conn.commit()

        if OWNER_ID:
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]

            await context.bot.send_message(
                OWNER_ID,
f"""<< دخول نفـرر جديد لبوتك >>

• الاسم❤️: {user.full_name}
• المعرف💁: @{user.username if user.username else 'لا يوجد'}
• الايدي🆔: {user.id}
• عدد مشتركينك: {total}"""
            )

    await update.message.reply_text(
        "مرحباً بك في بوت الأذكار 🌙",
        reply_markup=main_keyboard()
    )

    await random_reaction(update)

async def show_azkar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zikr = random.choice(AZKAR["general"])
    user_id = update.effective_user.id

    cur.execute("UPDATE users SET total_reads=total_reads+1 WHERE user_id=%s",(user_id,))
    conn.commit()

    await update.message.reply_text(f"📖 {zikr}")
    await random_reaction(update)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT total_reads FROM users WHERE user_id=%s",(user_id,))
    data = cur.fetchone()

    if data:
        count = data[0]
        rank = get_rank(count)

        await update.message.reply_text(
            f"📊 إحصائياتك\n\nعدد الأذكار: {count}\nرتبتك: {rank}"
        )

    await random_reaction(update)

async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}"
    await update.message.reply_text(f"🤝 رابط مشاركة البوت:\n{link}")
    await random_reaction(update)

# ==============================
# السبحة الاحترافية
# ==============================

TASBIH_ITEMS = [
    "سبحان الله",
    "الحمدلله",
    "لا اله الا الله",
    "الله اكبر"
]

def build_tasbih_keyboard(user_counts):
    keyboard = []
    for i, text in enumerate(TASBIH_ITEMS):
        count = user_counts.get(i, 0)
        keyboard.append([
            InlineKeyboardButton(f"{text}", callback_data="ignore"),
        ])
        keyboard.append([
            InlineKeyboardButton(f"🔢 {count}", callback_data=f"tasbih_{i}")
        ])
    keyboard.append([InlineKeyboardButton("🔄 تصفير الكل", callback_data="reset_all")])
    return InlineKeyboardMarkup(keyboard)

async def tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("tasbih_counts", {})
    keyboard = build_tasbih_keyboard(context.user_data["tasbih_counts"])

    await update.message.reply_text(
        "📿 السبحة الذكية\nاضغط على العداد لزيادة العدد",
        reply_markup=keyboard
    )
    await random_reaction(update)

async def tasbih_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    counts = context.user_data.setdefault("tasbih_counts", {})

    if query.data.startswith("tasbih_"):
        index = int(query.data.split("_")[1])
        counts[index] = counts.get(index, 0) + 1

    elif query.data == "reset_all":
        context.user_data["tasbih_counts"] = {}
        counts = {}

    keyboard = build_tasbih_keyboard(counts)
    await query.edit_message_reply_markup(reply_markup=keyboard)

# ==============================
# الإدارة
# ==============================

BROADCAST = 1

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    await update.message.reply_text(
        f"⚙️ لوحة المطور\n\nعدد المستخدمين: {total}"
    )

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return ConversationHandler.END

    await update.message.reply_text("أرسل رسالة الإذاعة الآن")
    return BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    sent = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(user[0], message)
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"📢 انتهت الإذاعة\n\n✅ تم: {sent}\n❌ فشل: {failed}"
    )
    return ConversationHandler.END

# ==============================
# Flask (لـ Render Web Service)
# ==============================

from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import asyncio
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

# ==============================
# إنشاء التطبيق
# ==============================

application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("admin", admin))

application.add_handler(ConversationHandler(
    entry_points=[CommandHandler("broadcast", broadcast_start)],
    states={
        BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]
    },
    fallbacks=[]
))

application.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), show_azkar))
application.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), stats))
application.add_handler(MessageHandler(filters.Regex("📿 السبحة"), tasbih))
application.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share_bot))

application.add_handler(CallbackQueryHandler(tasbih_handler))

# ==============================
# Webhook Route
# ==============================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

# ==============================
# التشغيل الصحيح لـ Render
# ==============================

if __name__ == "__main__":
    initialize_database()

    async def main():
        await application.initialize()
        await application.start()

        # تعيين الويبهوك (ضع رابط مشروعك هنا)
        await application.bot.set_webhook(
            url=f"https://YOUR-RENDER-APP.onrender.com/{BOT_TOKEN}"
        )

    asyncio.run(main())

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

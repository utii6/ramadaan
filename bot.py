import os
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
    ReplyKeyboardMarkup,
    WebAppInfo
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

logging.basicConfig(level=logging.INFO)

# ==============================
# قاعدة البيانات (تحسين الاتصال)
# ==============================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
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
    cur.close()
    conn.close()

# ==============================
# أدوات مساعدة
# ==============================
REACTIONS = ["❤️","✨","🤲","📿","🌙","🌟","💎","🌸"]

async def send_reaction(update: Update):
    """إرسال تفاعل حقيقي على الرسالة"""
    try:
        if update.message:
            # تتطلب إصدار python-telegram-bot 20.8+
            await update.message.set_reaction(reaction=random.choice(REACTIONS))
    except Exception as e:
        logging.error(f"Reaction Error: {e}")

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📖 الأذكار", "📿 السبحة"], ["📊 إحصائياتي", "🤝 مشاركة"]],
        resize_keyboard=True
    )

# ==============================
# الأوامر الأساسية
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (%s,%s,%s)",
            (user.id, user.username, user.full_name)
        )
        conn.commit()
        # إشعار المطور
        if OWNER_ID:
            await context.bot.send_message(OWNER_ID, f"👤 عضو جديد: {user.mention_html()}", parse_mode='HTML')

    cur.close()
    conn.close()
    
    await update.message.reply_text(
        f"مرحباً بك يا {user.first_name} في بوت الأذكار 🌙\nاستخدم الأزرار بالأسفل للتنقل.",
        reply_markup=main_keyboard()
    )
    await send_reaction(update)

async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text=انصحك بتجربة بوت الأذكار والسبحة الإلكترونية 🌙📿"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 إرسال الرابط لصديق", url=share_url)]
    ])
    
    await update.message.reply_text(
        "🤝 ساهم في نشر الخير وشارك البوت مع أصدقائك:",
        reply_markup=keyboard
    )
    await send_reaction(update)

# ==============================
# لوحة التحكم (المطورة)
# ==============================
BROADCAST = 1

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 إذاعة للكل", callback_data="admin_bc")],
        [InlineKeyboardButton("📊 تحديث الإحصائيات", callback_data="admin_stats")]
    ])
    
    await update.message.reply_text(
        f"⚙️ **لوحة التحكم**\n\n👥 عدد المشتركين: {count}",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "admin_bc":
        await query.message.reply_text("📥 أرسل الآن نص الإذاعة (أو أرسل /cancel للإلغاء):")
        return BROADCAST
    elif query.data == "admin_stats":
        await admin_panel(update, context)
    await query.answer()

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/cancel":
        await update.message.reply_text("❌ تم إلغاء الإذاعة.")
        return ConversationHandler.END

    msg = update.message.text
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    sent, fail = 0, 0
    for user in users:
        try:
            await context.bot.send_message(user[0], msg)
            sent += 1
            await asyncio.sleep(0.05) # تجنب الحظر
        except:
            fail += 1
            
    await update.message.reply_text(f"✅ تم الإرسال لـ {sent}\n❌ فشل لـ {fail}")
    return ConversationHandler.END

# ==============================
# تشغيل التطبيق
# ==============================
app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# إضافة الهاندرلرات
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("panel", admin_panel))
application.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share_bot))

# نظام الإذاعة
broadcast_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_bc$")],
    states={BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
)
application.add_handler(broadcast_handler)

# (أضف بقية الهاندرلرات الخاصة بالأذكار والسبحة هنا كما في كودك السابق)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        return "ok"

if __name__ == "__main__":
    initialize_database()
    # كود التشغيل الخاص بـ Render...
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

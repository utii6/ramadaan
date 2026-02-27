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
# الإعدادات الأساسية
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
RENDER_URL = "https://your-app-name.onrender.com" # استبدله برابطك

logging.basicConfig(level=logging.INFO)

# ==============================
# إدارة قاعدة البيانات
# ==============================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

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
# تحميل البيانات والأدوات
# ==============================
def load_azkar():
    try:
        with open("azkar.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"general": ["سُبْحَانَ اللَّهِ وَبِحَمْدِهِ", "أستغفر الله العظيم"]}

AZKAR = load_azkar()
REACTIONS = ["❤️","✨","🤲","📿","🌙","🌟","💎","🌸"]
TASBIH_ITEMS = ["سبحان الله", "الحمدلله", "لا اله الا الله", "الله اكبر"]

async def send_reaction(update: Update):
    try:
        if update.message:
            await update.message.set_reaction(random.choice(REACTIONS))
    except: pass

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📖 الأذكار", "📿 السبحة"], ["📊 إحصائياتي", "🤝 مشاركة"]],
        resize_keyboard=True
    )

# ==============================
# الأوامر والوظائف
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, full_name) VALUES (%s,%s,%s)",
                    (user.id, user.username, user.full_name))
        conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text("مرحباً بك في بوت الأذكار 🌙", reply_markup=main_keyboard())
    await send_reaction(update)

async def show_azkar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zikr = random.choice(AZKAR["general"])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=%s", (update.effective_user.id,))
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text(f"📖 {zikr}")
    await send_reaction(update)

async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_info = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_info.username}&text=انصحك بتجربة بوت الأذكار 🌙"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 مشاركة البوت الآن", url=share_url)]])
    await update.message.reply_text("🤝 ساهم في نشر الخير:", reply_markup=keyboard)

# ==============================
# نظام السبحة المتطور
# ==============================
def build_tasbih_keyboard(counts):
    keyboard = []
    for i, text in enumerate(TASBIH_ITEMS):
        c = counts.get(str(i), 0)
        keyboard.append([InlineKeyboardButton(f"{text} ({c})", callback_data=f"t_{i}")])
    keyboard.append([InlineKeyboardButton("🔄 تصفير", callback_data="t_reset")])
    return InlineKeyboardMarkup(keyboard)

async def tasbih_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counts = context.user_data.setdefault("t_counts", {})
    await update.message.reply_text("📿 السبحة الإلكترونية:", reply_markup=build_tasbih_keyboard(counts))

async def tasbih_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    counts = context.user_data.get("t_counts", {})

    if query.data.startswith("t_"):
        action = query.data.split("_")[1]
        if action == "reset": context.user_data["t_counts"] = {}
        else: counts[action] = counts.get(action, 0) + 1
        
        await query.edit_message_reply_markup(reply_markup=build_tasbih_keyboard(context.user_data["t_counts"]))

# ==============================
# لوحة التحكم (Admin)
# ==============================
BC_STATE = 1

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة جماعية", callback_data="adm_bc")]])
    await update.message.reply_text(f"⚙️ لوحة الإدارة\nالمستخدمين: {total}", reply_markup=kb)

async def bc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("أرسل نص الإذاعة الآن:")
    return BC_STATE

async def bc_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    
    for u in users:
        try: await context.bot.send_message(u[0], msg)
        except: pass
    await update.message.reply_text("✅ تمت الإذاعة بنجاح")
    return ConversationHandler.END

# ==============================
# Flask & Webhook Bridge
# ==============================
app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# إضافة جميع المعالجات
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("panel", admin_panel))
application.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), show_azkar))
application.add_handler(MessageHandler(filters.Regex("📿 السبحة"), tasbih_start))
application.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share_bot))
application.add_handler(CallbackQueryHandler(tasbih_handler, pattern="^t_"))
application.add_handler(ConversationHandler(
    entry_points=[CallbackQueryHandler(bc_start, pattern="^adm_bc$")],
    states={BC_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bc_finish)]},
    fallbacks=[]
))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    if not application.update_queue: await application.initialize()
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok", 200

@app.route("/")
def index(): return "Bot is Running", 200

if __name__ == "__main__":
    initialize_database()
    # تشغيل الويب هوك يدوياً عند بدء التطبيق
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.bot.set_webhook(f"{RENDER_URL}/{BOT_TOKEN}"))
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

import os
import logging
import random
import datetime
import psycopg2
import requests
import asyncio
from flask import Flask
from threading import Thread

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    constants
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

# ========= الإعدادات الأساسية =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourchannel") # معرف قناتك للاشتراك الإجباري
DATABASE_URL = os.getenv("DATABASE_URL")
AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

logging.basicConfig(level=logging.INFO)

# ========= قاعدة البيانات (الربط والإنشاء) =========
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def init_db():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_reads INTEGER DEFAULT 0,
            tasbih_count INTEGER DEFAULT 0,
            notifications_enabled BOOLEAN DEFAULT TRUE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

# ========= الأدوات والمساعدات =========
ALL_AZKAR = {}
BROADCAST = 1
REACTIONS_LIST = ["❤️", "✨", "🤲", "📿", "🌙", "🔥", "💎", "🌟"]

def fetch_azkar():
    global ALL_AZKAR
    if not ALL_AZKAR:
        try:
            r = requests.get(AZKAR_API)
            if r.status_code == 200: ALL_AZKAR = r.json()
        except: pass

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [constants.ChatMemberStatus.MEMBER, constants.ChatMemberStatus.ADMINISTRATOR, constants.ChatMemberStatus.OWNER]
    except:
        return False

def get_rank(count):
    if count < 100: return "🌱 مبتدئ"
    elif count < 500: return "✨ مداوم"
    elif count < 1000: return "📿 محب للذكر"
    return "🌟 من الذاكرين"

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📖 الأذكار", "📿 السبحة"], ["📊 إحصائياتي", "⚙️ الإعدادات"], ["🤝 مشاركة"]],
        resize_keyboard=True
    )

# ========= دوال المستخدم =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. الاشتراك الإجباري
    if not await is_subscribed(context.bot, user.id):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("اضغط هنا للاشتراك", url=f"https://t.me/{CHANNEL_ID[1:]}")]])
        await update.message.reply_text(f"⚠️ عذراً عزيزي، يجب عليك الاشتراك في قناة البوت أولاً لاستخدام ميزاته.\n\nبعد الاشتراك أرسل /start", reply_markup=kb)
        return

    # 2. إشعار المالك وحفظ البيانات
    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, full_name) VALUES (%s,%s,%s)", (user.id, user.username, user.full_name))
        conn.commit()
        # إشعار المالك لمرة واحدة فقط
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        await context.bot.send_message(OWNER_ID, f"🔔 انضم مستخدم جديد!\nالاسم: {user.full_name}\nالإجمالي الآن: {count}")

    # 3. واجهة الترحيب (خاصة للمالك / عامة للمستخدم)
    msg = f"مرحباً بك {user.first_name} في بوت الأذكار 🌙\n\nاستخدم القائمة أدناه للبدء في وردك اليومي."
    if user.id == OWNER_ID:
        msg += "\n\n⚙️ أهلاً بك يا مطوري، يمكنك استخدام /admin للتحكم."
    
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("☀️ أذكار الصباح", callback_data="az_أذكار الصباح"), InlineKeyboardButton("🌙 أذكار المساء", callback_data="az_أذكار المساء")],
        [InlineKeyboardButton("💤 أذكار النوم", callback_data="az_أذكار النوم"), InlineKeyboardButton("🕌 أدعية نبوية", callback_data="az_أدعية نبوية")]
    ])
    await update.message.reply_text("📖 اختر التصنيف المفضل لديك:", reply_markup=kb)

async def send_zekr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fetch_azkar()
    cat = query.data.split("_", 1)[1]
    items = ALL_AZKAR.get(cat, [])
    if not items: return
    
    item = random.choice(items)
    text = item.get("content") or item.get("zekr")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 ذكر آخر", callback_data=query.data), InlineKeyboardButton("✅ تمت القراءة", callback_data="done")]])
    await query.edit_message_text(f"*{cat}*\n\n{text}", reply_markup=kb, parse_mode="Markdown")

async def done_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cur.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=%s", (query.from_user.id,))
    conn.commit()
    await query.answer("تقبل الله منك! تم تسجيل القراءة في ملفك 📈")

async def tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (update.effective_user.id,))
    count = cur.fetchone()[0]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="ts_plus")], [InlineKeyboardButton("♻️ تصفير", callback_data="ts_zero")]])
    await update.message.reply_text("📿 السبحة الإلكترونية الذكية:", reply_markup=kb)

async def handle_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (query.from_user.id,))
    count = cur.fetchone()[0]
    
    count = count + 1 if query.data == "ts_plus" else 0
    cur.execute("UPDATE users SET tasbih_count=%s WHERE user_id=%s", (count, query.from_user.id))
    conn.commit()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="ts_plus")], [InlineKeyboardButton("♻️ تصفير", callback_data="ts_zero")]])
    await query.edit_message_reply_markup(reply_markup=kb)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT total_reads, tasbih_count FROM users WHERE user_id=%s", (update.effective_user.id,))
    data = cur.fetchone()
    reads, counts = data[0], data[1]
    await update.message.reply_text(f"📊 *ملف العبادة الخاص بك:*\n\n📖 الأذكار المقروءة: {reads}\n📿 إجمالي التسبيح: {counts}\n🏅 الرتبة: {get_rank(reads)}", parse_mode="Markdown")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT notifications_enabled FROM users WHERE user_id=%s", (update.effective_user.id,))
    status = cur.fetchone()[0]
    new_status = not status
    cur.execute("UPDATE users SET notifications_enabled=%s WHERE user_id=%s", (new_status, update.effective_user.id))
    conn.commit()
    await update.message.reply_text(f"⚙️ تم {'تفعيل' if new_status else 'إيقاف'} التنبيهات اليومية بنجاح.")

# ========= التفاعل العشوائي والذكاء =========
async def global_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        # نظام التفاعل (Reaction) التلقائي
        try:
            await update.message.set_reaction(reaction=random.choice(REACTIONS_LIST))
        except: pass

# ========= لوحة التحكم (Admin) =========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 إذاعة شاملة", callback_data="broadcast")], [InlineKeyboardButton("📊 إحصائيات القاعدة", callback_data="db_stats")]])
    await update.message.reply_text(f"🛠 لوحة المطور:\nعدد المشتركين الكلي: {total}", reply_markup=kb)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("أرسل الآن (نص، صورة، فيديو، بصمة) ليتم إرسالها للجميع:")
    return BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    success, fail = 0, 0
    for u in users:
        try:
            await update.message.copy(u[0])
            success += 1
            await asyncio.sleep(0.05) # حماية من الحظر
        except: fail += 1
    await update.message.reply_text(f"✅ انتهت الإذاعة:\nنجاح: {success}\nفشل (محظور): {fail}")
    return ConversationHandler.END

# ========= الجدولة والتشغيل =========
app = Flask('')
@app.route('/')
def home(): return "Bot is Online ✅"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def main():
    init_db()
    Thread(target=run_flask).start()
    
    app_ = Application.builder().token(BOT_TOKEN).build()
    
    # الإذاعة
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="broadcast")],
        states={BROADCAST: [MessageHandler(filters.ALL, broadcast_send)]},
        fallbacks=[]
    )
    
    # الروابط
    app_.add_handler(CommandHandler("start", start))
    app_.add_handler(CommandHandler("admin", admin_panel))
    app_.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), show_categories))
    app_.add_handler(MessageHandler(filters.Regex("📿 السبحة"), tasbih))
    app_.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), stats))
    app_.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), settings))
    app_.add_handler(CallbackQueryHandler(send_zekr, pattern="^az_"))
    app_.add_handler(CallbackQueryHandler(done_read, pattern="^done$"))
    app_.add_handler(CallbackQueryHandler(handle_tasbih, pattern="^ts_"))
    app_.add_handler(broadcast_conv)
    
    # التفاعل التلقائي على كل رسالة
    app_.add_handler(MessageHandler(filters.ALL, global_handler), group=1)
    
    app_.run_polling()

if __name__ == "__main__":
    main()

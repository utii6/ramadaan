import os, time, random, logging, psycopg2, requests, asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters

# ===============================
# إعدادات البيئة
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourchannel")
DATABASE_URL = os.getenv("DATABASE_URL")
AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# قاعدة البيانات
# ===============================
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def initialize_database():
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smm_users (
            user_id BIGINT PRIMARY KEY,
            last_sub REAL DEFAULT 0, last_view REAL DEFAULT 0,
            is_vip INTEGER DEFAULT 0, vip_expiry REAL DEFAULT 0,
            points INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    logger.info("تم تهيئة قاعدة البيانات.")

# ===============================
# بيانات الأذكار و Reactions
# ===============================
ALL_AZKAR = {}
BROADCAST_STATE = 1
REACTIONS_COLLECTION = ["❤️", "✨", "🤲", "📿", "🌙", "🌟", "💎", "☁️", "🌸"]

def fetch_azkar_data():
    global ALL_AZKAR
    if not ALL_AZKAR:
        try:
            r = requests.get(AZKAR_API)
            if r.status_code == 200:
                ALL_AZKAR = r.json()
        except Exception as e:
            logger.error(f"Error fetching azkar: {e}")

async def check_forced_subscription(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [constants.ChatMemberStatus.MEMBER, constants.ChatMemberStatus.ADMINISTRATOR, constants.ChatMemberStatus.OWNER]
    except: return False

def calculate_user_rank(read_count):
    if read_count < 100: return "🌱 مبتدئ"
    elif read_count < 500: return "✨ مداوم"
    elif read_count < 1000: return "📿 محب للذكر"
    elif read_count < 5000: return "🌟 من الذاكرين"
    return "👑 خادم السنة"

def create_main_markup():
    keyboard = [["📖 الأذكار", "📿 السبحة"], ["📊 إحصائياتي", "⚙️ الإعدادات"], ["🤝 مشاركة"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===============================
# أوامر المستخدم
# ===============================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_forced_subscription(context.bot, user.id):
        kb = [[InlineKeyboardButton("اشترك بالقناة 📢", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(f"⚠️ يرجى الاشتراك بالقناة {CHANNEL_ID}", reply_markup=InlineKeyboardMarkup(kb))
        return

    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, full_name) VALUES (%s,%s,%s)", (user.id, user.username, user.full_name))
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM users")
        total_count = cur.fetchone()[0]
        await context.bot.send_message(OWNER_ID, f"🔔 مستخدم جديد!\n👤 {user.full_name}\n🆔 {user.id}\n📈 إجمالي: {total_count}")

    welcome_text = f"أهلاً بك يا {user.first_name} في بوت الأذكار 🌙"
    if user.id == OWNER_ID:
        welcome_text += "\n🛠 يمكنك استخدام /admin للوصول للوحة التحكم"
    await update.message.reply_text(welcome_text, reply_markup=create_main_markup(), parse_mode="Markdown")

async def reaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        try: await update.message.set_reaction(random.choice(REACTIONS_COLLECTION))
        except: pass

# ===============================
# أذكار وسبحة
# ===============================
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("☀️ أذكار الصباح", callback_data="az_أذكار الصباح")],
        [InlineKeyboardButton("🌙 أذكار المساء", callback_data="az_أذكار المساء")],
        [InlineKeyboardButton("💤 أذكار النوم", callback_data="az_أذكار النوم")],
        [InlineKeyboardButton("🕌 أدعية نبوية", callback_data="az_أدعية نبوية")]
    ]
    await update.message.reply_text("📖 اختر التصنيف:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_azkar_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fetch_azkar_data()
    category = query.data.split("_",1)[1]
    azkar_list = ALL_AZKAR.get(category, [])
    if not azkar_list: return await query.edit_message_text("لا توجد بيانات حالياً.")
    content = random.choice(azkar_list).get("content") or random.choice(azkar_list).get("zekr")
    kb = [[InlineKeyboardButton("🔄 ذكر آخر", callback_data=query.data)],
          [InlineKeyboardButton("✅ تمت القراءة", callback_data="mark_as_read")]]
    await query.edit_message_text(f"✨ *{category}*\n\n{content}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def increment_read_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    cur.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=%s", (user_id,))
    conn.commit()
    await update.callback_query.answer("تم تسجيل القراءة ✨")

async def display_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (user_id,))
    count = cur.fetchone()[0]
    kb = [[InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="tasbih_plus")],
          [InlineKeyboardButton("♻️ تصفير العداد", callback_data="tasbih_reset")]]
    await update.message.reply_text("📿 السبحة:", reply_markup=InlineKeyboardMarkup(kb))

async def update_tasbih_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (user_id,))
    count = cur.fetchone()[0]
    count = count + 1 if query.data=="tasbih_plus" else 0
    cur.execute("UPDATE users SET tasbih_count=%s WHERE user_id=%s", (count, user_id))
    conn.commit()
    kb = [[InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="tasbih_plus")],
          [InlineKeyboardButton("♻️ تصفير العداد", callback_data="tasbih_reset")]]
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))

# ===============================
# الإحصائيات والإعدادات
# ===============================
async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT total_reads, tasbih_count, joined_at FROM users WHERE user_id=%s", (user_id,))
    reads, tasbihs, joined = cur.fetchone()
    rank = calculate_user_rank(reads)
    stats_text = f"📊 *ملفك:*\n🏅 {rank}\n📖 أذكار: {reads}\n📿 تسبيح: {tasbihs}\n📅 انضم: {joined.strftime('%Y-%m-%d')}"
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT notifications_enabled FROM users WHERE user_id=%s", (user_id,))
    new_status = not cur.fetchone()[0]
    cur.execute("UPDATE users SET notifications_enabled=%s WHERE user_id=%s", (new_status, user_id))
    conn.commit()
    await update.message.reply_text("✅ تفعيل التنبيهات" if new_status else "❌ إيقاف التنبيهات")

async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_info = await context.bot.get_me()
    await update.message.reply_text(f"شارك البوت: https://t.me/{bot_info.username}")

# ===============================
# لوحة المطور
# ===============================
async def open_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    kb = [[InlineKeyboardButton("📢 إذاعة شاملة", callback_data="admin_broadcast")],
          [InlineKeyboardButton("📊 إحصائيات القاعدة", callback_data="admin_db_info")]]
    await update.message.reply_text(f"🛠 لوحة المطور\n👥 إجمالي المستخدمين: {total}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("📥 أرسل المحتوى للجميع:")
    return BROADCAST_STATE

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT user_id FROM users")
    all_ids = cur.fetchall()
    success, fail = 0, 0
    await update.message.reply_text(f"⏳ بدأ الإرسال لـ {len(all_ids)} مستخدم...")
    for (uid,) in all_ids:
        try:
            await update.message.copy(chat_id=uid)
            success +=1
            await asyncio.sleep(0.05)
        except: fail +=1
    await update.message.reply_text(f"✅ نجاح: {success}\n❌ فشل: {fail}", parse_mode="Markdown")
    return ConversationHandler.END

# ===============================
# Keep-Alive Flask
# ===============================
web_app = Flask('')
@web_app.route('/')
def status_page(): return "<h1>Zekr Bot Live ✅</h1>"

def run_web_server(): web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# ===============================
# Main
# ===============================
def main():
    initialize_database()
    Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={BROADCAST_STATE:[MessageHandler(filters.ALL & ~filters.COMMAND, execute_broadcast)]},
        fallbacks=[]
    )
    
    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", open_admin_panel))
    app.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), list_categories))
    app.add_handler(MessageHandler(filters.Regex("📿 السبحة"), display_tasbih))
    app.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), show_user_stats))
    app.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), toggle_notifications))
    app.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share_bot))
    
    app.add_handler(CallbackQueryHandler(handle_azkar_request, pattern="^az_"))
    app.add_handler(CallbackQueryHandler(increment_read_count, pattern="^mark_as_read$"))
    app.add_handler(CallbackQueryHandler(update_tasbih_counter, pattern="^tasbih_"))
    app.add_handler(broadcast_handler)
    
    # Reactions
    app.add_handler(MessageHandler(filters.ALL, reaction_handler), group=1)
    
    print("--- البوت يعمل الآن بنظام Polling ---")
    app.run_polling()

if __name__ == "__main__":
    main()

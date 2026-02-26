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

# ==========================================
# الإعدادات الأساسية (Environment Variables)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@yourchannel")  # القناة الخاصة بالاشتراك الإجباري
DATABASE_URL = os.getenv("DATABASE_URL")
AZKAR_API = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

# إعداد السجلات (Logs) لمراقبة الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# إدارة قاعدة البيانات (PostgreSQL)
# ==========================================
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def initialize_database():
    """إنشاء الجداول اللازمة إذا لم تكن موجودة"""
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
    logger.info("تم فحص وإنشاء قاعدة البيانات بنجاح.")

# ==========================================
# الدوال المساعدة (Helper Functions)
# ==========================================
ALL_AZKAR = {}
BROADCAST_STATE = 1
REACTIONS_COLLECTION = ["❤️", "✨", "🤲", "📿", "🌙", "🌟", "💎", "☁️", "🌸"]

def fetch_azkar_data():
    """جلب بيانات الأذكار من المستودع الخارجي"""
    global ALL_AZKAR
    if not ALL_AZKAR:
        try:
            response = requests.get(AZKAR_API)
            if response.status_code == 200:
                ALL_AZKAR = response.json()
        except Exception as e:
            logger.error(f"Error fetching azkar: {e}")

async def check_forced_subscription(bot, user_id):
    """التحقق من اشتراك المستخدم في القناة (الاشتراك الإجباري)"""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in [constants.ChatMemberStatus.MEMBER, 
                            constants.ChatMemberStatus.ADMINISTRATOR, 
                            constants.ChatMemberStatus.OWNER]:
            return True
        return False
    except Exception:
        return False

def calculate_user_rank(read_count):
    """تحديد رتبة المستخدم بناءً على نشاطه"""
    if read_count < 100:
        return "🌱 مبتدئ"
    elif read_count < 500:
        return "✨ مداوم"
    elif read_count < 1000:
        return "📿 محب للذكر"
    elif read_count < 5000:
        return "🌟 من الذاكرين"
    else:
        return "👑 خادم السنة"

def create_main_markup():
    """لوحة أزرار التحكم الرئيسية"""
    keyboard = [
        ["📖 الأذكار", "📿 السبحة"],
        ["📊 إحصائياتي", "⚙️ الإعدادات"],
        ["🤝 مشاركة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==========================================
# معالجة الأوامر الرئيسية (User Side)
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية مع نظام الترحيب والتحقق من الاشتراك"""
    user = update.effective_user
    
    # التحقق من الاشتراك الإجباري
    is_sub = await check_forced_subscription(context.bot, user.id)
    if not is_sub:
        keyboard = [[InlineKeyboardButton("اضغط للاشتراك في القناة 📢", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⚠️ يرجى الاشتراك في القناة أولاً لاستخدام البوت:\n{CHANNEL_ID}",
            reply_markup=reply_markup
        )
        return

    # فحص المستخدم في القاعدة
    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user.id,))
    existing_user = cur.fetchone()
    
    if not existing_user:
        # إضافة مستخدم جديد
        cur.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (%s, %s, %s)",
            (user.id, user.username, user.full_name)
        )
        conn.commit()
        
        # إرسال إشعار للمالك
        cur.execute("SELECT COUNT(*) FROM users")
        total_count = cur.fetchone()[0]
        await context.bot.send_message(
            OWNER_ID,
            f"🔔 *مستخدم جديد انضم!*\n\n"
            f"👤 الاسم: {user.full_name}\n"
            f"🆔 الآيدي: {user.id}\n"
            f"📈 إجمالي المشتركين: {total_count}",
            parse_mode="Markdown"
        )

    welcome_text = (
        f"أهلاً بك يا {user.first_name} في بوت الأذكار الشامل 🌙\n\n"
        "هذا البوت صدقة جارية، يمكنك قراءة الأذكار، التسبيح، ومتابعة إحصائياتك اليومية."
    )
    
    if user.id == OWNER_ID:
        welcome_text += "\n\n🛠 *مرحباً يا مطوري!* يمكنك استخدام /admin للدخول للوحة التحكم."

    await update.message.reply_text(welcome_text, reply_markup=create_main_markup(), parse_mode="Markdown")

async def reaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وضع تفاعل (Reaction) على كل رسالة يرسلها المستخدم"""
    if update.message:
        try:
            chosen_emoji = random.choice(REACTIONS_COLLECTION)
            await update.message.set_reaction(reaction=chosen_emoji)
        except Exception:
            pass

# ==========================================
# قسم الأذكار والسبحة
# ==========================================

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تصنيفات الأذكار"""
    keyboard = [
        [InlineKeyboardButton("☀️ أذكار الصباح", callback_data="az_أذكار الصباح")],
        [InlineKeyboardButton("🌙 أذكار المساء", callback_data="az_أذكار المساء")],
        [InlineKeyboardButton("💤 أذكار النوم", callback_data="az_أذكار النوم")],
        [InlineKeyboardButton("🕌 أدعية نبوية", callback_data="az_أدعية نبوية")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📖 اختر التصنيف الذي تريد قراءته:", reply_markup=reply_markup)

async def handle_azkar_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال ذكر عشوائي من التصنيف المختار"""
    query = update.callback_query
    await query.answer()
    
    fetch_azkar_data()
    category_name = query.data.split("_", 1)[1]
    azkar_list = ALL_AZKAR.get(category_name, [])
    
    if not azkar_list:
        await query.edit_message_text("عذراً، لا توجد بيانات حالياً.")
        return

    random_zekr = random.choice(azkar_list)
    content = random_zekr.get("content") or random_zekr.get("zekr")
    
    keyboard = [
        [InlineKeyboardButton("🔄 ذكر آخر", callback_data=query.data)],
        [InlineKeyboardButton("✅ تمت القراءة", callback_data="mark_as_read")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✨ *{category_name}*\n\n{content}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def increment_read_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زيادة عداد القراءات للمستخدم"""
    query = update.callback_query
    user_id = query.from_user.id
    
    cur.execute("UPDATE users SET total_reads = total_reads + 1 WHERE user_id=%s", (user_id,))
    conn.commit()
    
    await query.answer("بارك الله فيك، تم تسجيل القراءة في ميزان حسناتك ✨")

async def display_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة السبحة الذكية"""
    user_id = update.effective_user.id
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (user_id,))
    current_count = cur.fetchone()[0]
    
    keyboard = [
        [InlineKeyboardButton(f"➕ سبّح ({current_count})", callback_data="tasbih_plus")],
        [InlineKeyboardButton("♻️ تصفير العداد", callback_data="tasbih_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📿 السبحة الإلكترونية التفاعلية:", reply_markup=reply_markup)

async def update_tasbih_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث عداد السبحة بدون رسائل جديدة"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cur.execute("SELECT tasbih_count FROM users WHERE user_id=%s", (user_id,))
    count = cur.fetchone()[0]
    
    if query.data == "tasbih_plus":
        count += 1
    else:
        count = 0
        
    cur.execute("UPDATE users SET tasbih_count=%s WHERE user_id=%s", (count, user_id))
    conn.commit()
    
    keyboard = [
        [InlineKeyboardButton(f"➕ سبّح ({count})", callback_data="tasbih_plus")],
        [InlineKeyboardButton("♻️ تصفير العداد", callback_data="tasbih_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup=reply_markup)

# ==========================================
# الإحصائيات والإعدادات
# ==========================================

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدم التفصيلية"""
    user_id = update.effective_user.id
    cur.execute("SELECT total_reads, tasbih_count, joined_at FROM users WHERE user_id=%s", (user_id,))
    data = cur.fetchone()
    
    reads, tasbihs, joined = data[0], data[1], data[2]
    rank = calculate_user_rank(reads)
    
    stats_text = (
        f"📊 *ملف العبادة الخاص بك:*\n\n"
        f"🏅 الرتبة: {rank}\n"
        f"📖 عدد الأذكار: {reads}\n"
        f"📿 إجمالي التسبيح: {tasbihs}\n"
        f"📅 تاريخ الانضمام: {joined.strftime('%Y-%m-%d')}"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير حالة التنبيهات"""
    user_id = update.effective_user.id
    cur.execute("SELECT notifications_enabled FROM users WHERE user_id=%s", (user_id,))
    current_status = cur.fetchone()[0]
    
    new_status = not current_status
    cur.execute("UPDATE users SET notifications_enabled=%s WHERE user_id=%s", (new_status, user_id))
    conn.commit()
    
    status_msg = "✅ تم تفعيل التنبيهات اليومية" if new_status else "❌ تم إيقاف التنبيهات"
    await update.message.reply_text(status_msg)

async def share_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رابط مشاركة البوت"""
    bot_info = await context.bot.get_me()
    share_text = (
        f"أدعوكم لاستخدام بوت الأذكار (صدقة جارية) 🌙\n"
        f"يمكنك قراءة الأذكار ومتابعة وردك اليومي من هنا:\n"
        f"https://t.me/{bot_info.username}"
    )
    await update.message.reply_text(share_text)

# ==========================================
# لوحة التحكم (Admin Panel)
# ==========================================

async def open_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح لوحة المطور"""
    if update.effective_user.id != OWNER_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    keyboard = [
        [InlineKeyboardButton("📢 إذاعة شاملة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 إحصائيات القاعدة", callback_data="admin_db_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🛠 *لوحة تحكم المطور*\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"📡 حالة الخادم: يعمل ✅",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية عملية الإذاعة"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📥 أرسل الآن المحتوى الذي تريد إرساله للجميع (نص، صورة، فيديو، إلخ):")
    return BROADCAST_STATE

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ الإرسال للجميع مع حماية من الحظر"""
    cur.execute("SELECT user_id FROM users")
    all_ids = cur.fetchall()
    
    success_count, fail_count = 0, 0
    await update.message.reply_text(f"⏳ بدأت عملية الإذاعة لـ {len(all_ids)} مستخدم...")
    
    for (uid,) in all_ids:
        try:
            await update.message.copy(chat_id=uid)
            success_count += 1
            await asyncio.sleep(0.05) # تأخير بسيط لتجنب سبام تليجرام
        except Exception:
            fail_count += 1
            
    await update.message.reply_text(
        f"✅ *اكتملت الإذاعة*\n\n"
        f"✅ نجاح: {success_count}\n"
        f"❌ فشل (بلوك): {fail_count}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==========================================
# Keep-Alive (Flask)
# ==========================================
web_app = Flask('')

@web_app.route('/')
def status_page():
    return "<h1>Zekr Bot is Live!</h1><p>Status: Healthy ✅</p>"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# ==========================================
# تشغيل البوت (Main Loop)
# ==========================================

def main():
    # 1. تهيئة البيانات والقاعدة
    initialize_database()
    
    # 2. تشغيل سيرفر الويب في خلفية مستقلة
    Thread(target=run_web_server, daemon=True).start()
    
    # 3. بناء تطبيق التليجرام
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 4. تعريف محادثة الإذاعة
    broadcast_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={
            BROADCAST_STATE: [MessageHandler(filters.ALL & ~filters.COMMAND, execute_broadcast)]
        },
        fallbacks=[]
    )
    
    # 5. إضافة المعالجات (Handlers)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", open_admin_panel))
    
    # معالجات الأزرار النصية
    application.add_handler(MessageHandler(filters.Regex("📖 الأذكار"), list_categories))
    application.add_handler(MessageHandler(filters.Regex("📿 السبحة"), display_tasbih))
    application.add_handler(MessageHandler(filters.Regex("📊 إحصائياتي"), show_user_stats))
    application.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), toggle_notifications))
    application.add_handler(MessageHandler(filters.Regex("🤝 مشاركة"), share_bot))
    
    # معالجات الـ Callback (الأزرار الشفافة)
    application.add_handler(CallbackQueryHandler(handle_azkar_request, pattern="^az_"))
    application.add_handler(CallbackQueryHandler(increment_read_count, pattern="^mark_as_read$"))
    application.add_handler(CallbackQueryHandler(update_tasbih_counter, pattern="^tasbih_"))
    
    # إضافة محادثة الإدارة
    application.add_handler(broadcast_handler)
    
    # التفاعل التلقائي (Reaction) على أي رسالة أخرى
    application.add_handler(MessageHandler(filters.ALL, reaction_handler), group=1)
    
    # 6. بدء التشغيل
    print("--- البوت يعمل الآن بنظام Polling ---")
    application.run_polling()

if __name__ == "__main__":
    main()

import os
import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReactionTypeEmoji, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web
from supabase import create_client, Client

# استدعاء ملف الأذكار (تأكد من وجود ملف اسمه azkar.py بجانبه)
import azkar 

# --- الإعدادات (تأكد من وضعها في Render) ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# تهيئة البوت وقاعدة البيانات
bot = Bot(token=TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- وظائف قاعدة البيانات (Supabase) ---
async def add_user_to_db(user_id, username, full_name):
    try:
        # محاولة إضافة المستخدم، إذا كان موجوداً سيفشل الطلب وهذا المطلوب (لمنع التكرار)
        supabase.table("users").insert({
            "user_id": user_id, 
            "username": username
        }).execute()
        return True
    except:
        return False

async def get_users_count():
    res = supabase.table("users").select("user_id", count="exact").execute()
    return res.count

async def get_setting(key_name):
    res = supabase.table("settings").select("value").eq("key", key_name).execute()
    return res.data[0]['value'] if res.data else None

# --- خادم الويب (للبقاء حياً على Render) ---
async def handle(request): return web.Response(text="Bot is Live!")
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# --- لوحة المفاتيح الشفافة (Inline) ---
def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="☀️ أذكار الصباح", callback_data="azkar_morning"))
    builder.row(InlineKeyboardButton(text="🌙 أذكار المساء", callback_data="azkar_evening"))
    builder.row(InlineKeyboardButton(text="📜 أذكار متنوعة", callback_data="azkar_random"))
    return builder.as_markup()

# --- معالجة الأوامر ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # تفاعل إيموجي
    try: await message.react([ReactionTypeEmoji(emoji="❤️‍🔥")])
    except: pass

    uid = message.from_user.id
    uname = message.from_user.username or "بدون يوزر"
    fname = message.from_user.full_name

    # محاولة إضافة المستخدم وإشعار المالك
    is_new = await add_user_to_db(uid, uname, fname)
    if is_new:
        total = await get_users_count()
        msg = f"👤 **مستخدم جديد انضم!**\n\n🔹 الاسم: {fname}\n🔹 اليوزر: @{uname}\n🔹 الآيدي: `{uid}`\n\n📈 العدد الإجمالي: {total}"
        try: await bot.send_message(OWNER_ID, msg, parse_mode="Markdown")
        except: pass

    welcome = await get_setting("welcome_msg") or "مرحباً بك في بوت الأذكار"
    
    # أزرار سفلية دائمة
    kb = ReplyKeyboardBuilder()
    kb.button(text="📖 القائمة الرئيسية")
    if uid == OWNER_ID: kb.button(text="⚙️ لوحة التحكم")
    
    await message.answer(welcome, reply_markup=kb.as_markup(resize_keyboard=True))
    await message.answer("اختر من الأذكار أدناه:", reply_markup=main_menu_kb())

@dp.callback_query(F.data.startswith("azkar_"))
async def handle_azkar(call: CallbackQuery):
    category = call.data.split("_")[1]
    
    if category == "morning":
        txt = random.choice(azkar.MORNING_AZKAR)
        title = "☀️ أذكار الصباح"
    elif category == "evening":
        txt = random.choice(azkar.EVENING_AZKAR)
        title = "🌙 أذكار المساء"
    else:
        txt = random.choice(azkar.RANDOM_AZKAR)
        title = "📜 ذكر متنوع"

    await call.message.answer(f"✨ **{title}**\n\n{txt}", parse_mode="Markdown")
    await call.answer()

# --- التشغيل ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())

import os
import random
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from supabase import create_client, Client

# --- الإعدادات الأساسية ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AZKAR_DATA_URL = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

# تهيئة البوت والديسباتشر وقاعدة البيانات
bot = Bot(token=TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ALL_AZKAR = {}

# --- وظائف جلب البيانات وقاعدة البيانات ---

async def fetch_azkar():
    global ALL_AZKAR
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(AZKAR_DATA_URL) as response:
                if response.status == 200:
                    ALL_AZKAR = await response.json()
                    logging.info("✅ الأذكار جاهزة")
        except Exception as e:
            logging.error(f"❌ خطأ جلب الأذكار: {e}")

async def add_user(user: types.User):
    try:
        # إضافة أو تحديث بيانات المستخدم
        supabase.table("users").upsert({
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name
        }).execute()
        return True
    except: return False

async def get_stats():
    res = supabase.table("users").select("user_id", count="exact").execute()
    return res.count

# --- لوحات المفاتيح ---

def main_menu_kb():
    builder = InlineKeyboardBuilder()
    cats = [("☀️ الصباح", "az_أذكار الصباح"), ("🌙 المساء", "az_أذكار المساء"), 
            ("💤 النوم", "az_أذكار النوم"), ("🕌 الصلاة", "az_أذكار الصلاة"),
            ("📿 بعد الصلاة", "az_أذكار بعد الصلاة"), ("🌟 أدعية نبوية", "az_أدعية نبوية")]
    for text, data in cats:
        builder.add(InlineKeyboardButton(text=text, callback_data=data))
    builder.adjust(2)
    return builder.as_markup()

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📊 عدد المستخدمين", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="📢 إذاعة (قريباً)", callback_data="admin_broadcast"))
    return builder.as_markup()

# --- معالجة الرسائل والأوامر ---

@dp.message()
async def auto_reaction_and_process(message: Message):
    # التفاعل التلقائي على أي رسالة تصل للبوت
    try:
        await message.react([ReactionTypeEmoji(emoji=random.choice(["❤️", "✨", "📿", "🌟"]))])
    except: pass

    # إذا كان الأمر /start
    if message.text == "/start":
        is_new = await add_user(message.from_user)
        if is_new:
            total = await get_stats()
            # إشعار المالك
            try:
                await bot.send_message(OWNER_ID, f"🔔 **مستخدم جديد!**\nالاسم: {message.from_user.full_name}\nاليوزر: @{message.from_user.username}\nالعدد الكلي: {total}")
            except: pass
        
        await message.answer("🌸 **مرحباً بك في بوت الأذكار النهائي**\nاستخدم القائمة أدناه لذكر الله:", reply_markup=main_menu_kb())

    # أمر الإدارة
    elif message.text == "/admin":
        if message.from_user.id == OWNER_ID:
            await message.answer("🔐 **لوحة تحكم المالك**", reply_markup=admin_kb())
        else:
            await message.answer("❌ عذراً، هذا الأمر للمالك فقط.")

# --- معالجة الضغط على الأزرار ---

@dp.callback_query(F.data.startswith("az_"))
async def handle_azkar(call: CallbackQuery):
    category = call.data.split("_")[1]
    if not ALL_AZKAR: await fetch_azkar()
    
    lst = ALL_AZKAR.get(category, [])
    if lst:
        item = random.choice(lst)
        txt = item.get('content') or item.get('zekr')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 ذكر آخر", callback_data=call.data)],
            [InlineKeyboardButton(text="🔙 العودة", callback_data="back")]
        ])
        await call.message.edit_text(f"✨ **{category}**\n\n{txt}", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "back")
async def go_back(call: CallbackQuery):
    await call.message.edit_text("اختر من القائمة:", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "admin_stats")
async def show_stats(call: CallbackQuery):
    count = await get_stats()
    await call.answer(f"عدد المستخدمين الحالي: {count}", show_alert=True)

# --- التشغيل النهائي ---

async def main():
    logging.basicConfig(level=logging.INFO)
    await fetch_azkar()
    # تنظيف العمليات القديمة
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("❌البوت توقف!")

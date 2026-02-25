import os
import random
import logging
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web
from supabase import create_client, Client

# --- الإعدادات ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# رابط قاعدة بيانات الأذكار الشاملة (JSON)
AZKAR_DATA_URL = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

# تهيئة البوت وقاعدة البيانات
bot = Bot(token=TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- جلب الأذكار من الرابط الخارجي ---
def load_remote_azkar():
    try:
        response = requests.get(AZKAR_DATA_URL)
        return response.json()
    except Exception as e:
        logging.error(f"Error loading azkar: {e}")
        return {}

# تخزين الأذكار في ذاكرة البوت عند التشغيل
ALL_AZKAR = load_remote_azkar()

def get_random_zekr(category_name):
    category_list = ALL_AZKAR.get(category_name, [])
    if category_list:
        selected = random.choice(category_list)
        # الرابط أحياناً يستخدم مفتاح 'content' وأحياناً 'zekr'
        return selected.get('content') or selected.get('zekr') or "عذراً، لم نتمكن من جلب النص."
    return "لا توجد أذكار في هذا التصنيف حالياً."

# --- وظائف Supabase ---
async def add_user_to_db(user_id, username):
    try:
        supabase.table("users").insert({"user_id": user_id, "username": username}).execute()
        return True
    except: return False

# --- لوحة المفاتيح الشاملة ---
def main_menu_kb():
    builder = InlineKeyboardBuilder()
    # تقسيم الأزرار بشكل منظم
    buttons = [
        ("☀️ أذكار الصباح", "az_أذكار الصباح"),
        ("🌙 أذكار المساء", "az_أذكار المساء"),
        ("💤 أذكار النوم", "az_أذكار النوم"),
        ("🕌 أذكار الصلاة", "az_أذكار الصلاة"),
        ("📿 بعد الصلاة", "az_أذكار بعد الصلاة"),
        ("📖 أدعية قرآنية", "az_أدعية قرآنية"),
        ("🌟 أدعية نبوية", "az_أدعية نبوية"),
        ("⛅ أذكار الاستيقاظ", "az_أذكار الاستيقاظ")
    ]
    for text, callback in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback))
    
    builder.adjust(2) # وضع زرين في كل صف
    return builder.as_markup()

# --- معالجة الأوامر ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    uname = message.from_user.username
    
    # إضافة المستخدم لـ Supabase
    await add_user_to_db(uid, uname)
    
    welcome_text = "🌸 **مرحباً بك في بوت الأذكار الشامل**\n\nتم تحديث البوت ليدمج مئات الأذكار والأدعية من المصادر الموثوقة. اختر ما تريد من القائمة أدناه:"
    
    # أزرار ثابتة بالأسفل
    reply_kb = ReplyKeyboardBuilder()
    reply_kb.button(text="📖 القائمة الرئيسية")
    
    await message.answer(welcome_text, reply_markup=reply_kb.as_markup(resize_keyboard=True), parse_mode="Markdown")
    await message.answer("القائمة:", reply_markup=main_menu_kb())

@dp.callback_query(F.data.startswith("az_"))
async def handle_azkar(call: CallbackQuery):
    category = call.data.split("_")[1]
    txt = get_random_zekr(category)
    
    # إرسال الذكر مع زر "ذكر آخر" من نفس النوع
    refresh_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ذكر آخر من نفس النوع", callback_data=f"az_{category}")],
        [InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="back_to_menu")]
    ])
    
    await call.message.edit_text(f"✨ **{category}**\n\n{txt}\n\n---", reply_markup=refresh_kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_menu(call: CallbackQuery):
    await call.message.edit_text("اختر من الأذكار أدناه:", reply_markup=main_menu_kb())
    await call.answer()

# --- تشغيل البوت ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

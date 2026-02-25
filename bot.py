import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, ReactionTypeEmoji

# --- الإعدادات الأساسية (يفضل وضعها في Environment Variables على Render) ---
TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 5581457665  # استبدله بـ ID حسابك
CHANNEL_ID = "@qd3qd" # يوزر القناة للاشتراك الإجباري
WELCOME_MSG = "مرحباً بك في بوت الأذكار 🌸"

# --- قاعدة بيانات مبسطة (في الواقع يفضل استخدام SQLite) ---
data = {
    "azkar": ["أصبحنا وأصبح الملك لله", "سبحان الله وبحمده"],
    "users": set(),
    "welcome_msg": WELCOME_MSG,
    "channel": CHANNEL_ID
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- وظائف مساعدة ---
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(data["channel"], user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return True # إذا لم يتم تعيين قناة يعمل البوت بشكل طبيعي

# --- التعامل مع أمر /start ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # إضافة التفاعل ❤️‍🔥
    try:
        await message.react([ReactionTypeEmoji(emoji="❤️‍🔥")])
    except: pass
    
    data["users"].add(message.from_user.id)
    
    # تحقق الاشتراك الإجباري
    if not await is_subscribed(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.button(text="اضغط هنا للاشتراك", url=f"https://t.me/{data['channel'].replace('@','')}")
        return await message.answer(f"⚠️ عذراً، يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:\n{data['channel']}", reply_markup=builder.as_markup())

    # القائمة الرئيسية
    kb = ReplyKeyboardBuilder()
    kb.button(text="📖 تصفح الأذكار")
    kb.button(text="⚙️ الإعدادات" if message.from_user.id == OWNER_ID else "ℹ️ عن البوت")
    kb.adjust(2)
    
    await message.answer(data["welcome_msg"], reply_markup=kb.as_markup(resize_keyboard=True))

# --- لوحة التحكم (الأدمن) ---
@dp.message(F.text == "⚙️ الإعدادات", F.from_user.id == OWNER_ID)
async def admin_panel(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 الإحصائيات", callback_data="stats")
    kb.button(text="📢 تغيير القناة", callback_data="set_channel")
    kb.button(text="📝 رسالة الترحيب", callback_data="set_welcome")
    kb.button(text="➕ إضافة ذكر", callback_data="add_zekr")
    kb.adjust(2)
    await message.answer("🛠 لوحة تحكم المالك:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    await call.answer(f"👥 عدد المستخدمين: {len(data['users'])}\n📜 عدد الأذكار: {len(data['azkar'])}", show_alert=True)

# --- نظام تصفح الأذكار ---
@dp.message(F.text == "📖 تصفح الأذكار")
async def show_azkar(message: Message):
    if not data["azkar"]:
        return await message.answer("لا توجد أذكار حالياً.")
    
    text = f"✨ **من أذكارنا:**\n\n{data['azkar'][0]}" # يعرض أول ذكر كمثال
    await message.answer(text, parse_mode="Markdown")

# --- تشغيل البوت ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

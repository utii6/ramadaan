import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, ReactionTypeEmoji
from aiohttp import web # لإبقاء البوت مستيقظاً

# --- الإعدادات ---
TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 5581457665  # ID حسابك
CHANNEL_ID = "@Qd3Qd" 
WELCOME_MSG = "مرحباً بك في بوت الأذكار 🌸"

# تخزين مؤقت (سيتم مسحه عند إعادة تشغيل السيرفر - سنحل هذا لاحقاً بـ SQLite)
data = {
    "azkar": ["أصبحنا وأصبح الملك لله", "سبحان الله وبحمده"],
    "users": set(),
    "welcome_msg": WELCOME_MSG,
    "channel": CHANNEL_ID
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- خادم ويب وهمي لإبقاء Render مستيقظاً ---
async def handle(request):
    return web.Response(text="I am alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# --- منطق البوت ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    try: await message.react([ReactionTypeEmoji(emoji="❤️‍🔥")])
    except: pass
    
    data["users"].add(message.from_user.id)
    
    # التحقق من الاشتراك
    try:
        chat_member = await bot.get_chat_member(data["channel"], message.from_user.id)
        if chat_member.status in ['left', 'kicked']:
            raise Exception()
    except:
        kb = InlineKeyboardBuilder()
        kb.button(text="الاشتراك في القناة", url=f"https://t.me/{data['channel'].replace('@','')}")
        return await message.answer(f"الرجاء الاشتراك في القناة أولاً: {data['channel']}", reply_markup=kb.as_markup())

    kb = ReplyKeyboardBuilder()
    kb.button(text="📖 تصفح الأذكار")
    if message.from_user.id == OWNER_ID:
        kb.button(text="⚙️ لوحة التحكم")
    
    await message.answer(data["welcome_msg"], reply_markup=kb.as_markup(resize_keyboard=True))

# لوحة التحكم (إحصائيات بسيطة)
@dp.message(F.text == "⚙️ لوحة التحكم", F.from_user.id == OWNER_ID)
async def admin(message: Message):
    await message.answer(f"📊 الإحصائيات:\n- عدد المستخدمين: {len(data['users'])}\n- عدد الأذكار: {len(data['azkar'])}")

# --- تشغيل الكل ---
async def main():
    logging.basicConfig(level=logging.INFO)
    # تشغيل خادم الويب والبوت معاً
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())

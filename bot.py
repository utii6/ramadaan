import os, random, logging, asyncio, aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from supabase import create_client, Client

# --- الإعدادات ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CHANNEL_ID = "@YourChannel"  # ضع يوزر قناتك هنا

AZKAR_URL = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ALL_AZKAR = {}

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()

# --- وظائف البيانات ---

async def fetch_azkar():
    global ALL_AZKAR
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(AZKAR_URL) as r:
                if r.status == 200: ALL_AZKAR = await r.json()
        except: pass

async def is_subbed(user_id):
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return m.status in ["member", "administrator", "creator"]
    except: return True

def get_rank(count):
    if count < 100: return "🌱 ذاكر مبتدئ"
    if count < 500: return "✨ مستغفر مداوم"
    if count < 1000: return "📿 محب للذكر"
    return "🌟 من الذاكرين كثيراً"

# --- لوحات المفاتيح ---

def main_reply_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="📖 الأذكار الشاملة"), b.button(text="📿 السبحة الإلكترونية")
    b.button(text="📊 إحصائياتي"), b.button(text="🤝 صدقة جارية")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)

def azkar_cats_kb():
    b = InlineKeyboardBuilder()
    cats = [("☀️ الصباح", "az_أذكار الصباح"), ("🌙 المساء", "az_أذكار المساء"), 
            ("💤 النوم", "az_أذكار النوم"), ("🕌 الصلاة", "az_أذكار الصلاة"),
            ("📖 أدعية قرآنية", "az_أدعية قرآنية"), ("🌟 أدعية نبوية", "az_أدعية نبوية")]
    for t, d in cats: b.add(InlineKeyboardButton(text=t, callback_data=d))
    b.adjust(2)
    return b.as_markup()

# --- المعالجات الرئيسية ---

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    try: await msg.react([ReactionTypeEmoji(emoji="❤️")])
    except: pass
    
    if not await is_subbed(msg.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 اشترك في القناة", url=f"t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="✅ تم الاشتراك", callback_data="check_sub")]
        ])
        return await msg.answer(f"✨ **أهلاً بك في بوت الأذكار**\n\nعذراً، يجب الاشتراك في القناة أولاً:", reply_markup=kb)

    # تسجيل المستخدم
    try:
        db.table("users").upsert({"user_id": msg.from_user.id, "username": msg.from_user.username, "full_name": msg.from_user.full_name}).execute()
        await bot.send_message(OWNER_ID, f"🔔 **مستخدم جديد**\nالاسم: {msg.from_user.full_name}\nاليوزر: @{msg.from_user.username}")
    except: pass

    await msg.answer(f"✨ **مرحباً بك يا {msg.from_user.first_name}**\n\nأهلاً بك في بوت الأذكار الشامل بلمساته الجديدة. تقبل الله منا ومنكم صالح الأعمال.", reply_markup=main_reply_kb())

@dp.message(F.text == "📖 الأذكار الشاملة")
async def show_cats(msg: Message):
    await msg.answer("🗂 **اختر التصنيف الذي تريد قراءته:**", reply_markup=azkar_cats_kb())

@dp.message(F.text == "📊 إحصائياتي")
async def my_stats(msg: Message):
    res = db.table("users").select("total_reads").eq("user_id", msg.from_user.id).single().execute()
    count = res.data.get('total_reads', 0) if res.data else 0
    rank = get_rank(count)
    await msg.answer(f"━━━━━━━━━━━━\n👤 **ملف العبادة الخاص بك**\n\n✨ عدد الأذكار المقروءة: `{count}`\n🏅 رتبتك: {rank}\n━━━━━━━━━━━━")

@dp.message(F.text == "📿 السبحة الإلكترونية")
async def tasbih_start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سبّح (0)", callback_data="ts_1")],
        [InlineKeyboardButton(text="🔄 تصفير", callback_data="ts_0")]
    ])
    await msg.answer("📿 **السبحة الإلكترونية**\n\nاضغط على الزر أدناه للبدء بالتسبيح:", reply_markup=kb)

@dp.message(F.text == "🤝 صدقة جارية")
async def share_bot(msg: Message):
    me = await bot.get_me()
    await msg.answer(f"✨ **ساهم في نشر الخير**\n\nشارك البوت مع أصدقائك ليكون لك صدقة جارية:\nhttps://t.me/{me.username}")

# --- معالجة الأزرار الشفافة ---

@dp.callback_query(F.data.startswith("az_"))
async def send_zekr(call: CallbackQuery):
    cat = call.data.split("_")[1]
    if not ALL_AZKAR: await fetch_azkar()
    item = random.choice(ALL_AZKAR.get(cat, [{"content": "حدث خطأ"}]))
    txt = item.get("content") or item.get("zekr")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ذكر آخر", callback_data=call.data)],
        [InlineKeyboardButton(text="✅ تمت القراءة", callback_data="done_read")],
        [InlineKeyboardButton(text="🔙 القائمة", callback_data="back_cats")]
    ])
    await call.message.edit_text(f"━━━━━━━━━━━━\n✨ **{cat}**\n\n{txt}\n━━━━━━━━━━━━", reply_markup=kb)

@dp.callback_query(F.data == "done_read")
async def done_read(call: CallbackQuery):
    try: db.rpc('increment_reads', {'u_id': call.from_user.id}).execute()
    except: pass
    await call.answer("تقبل الله منك! ✨")

@dp.callback_query(F.data.startswith("ts_"))
async def handle_tasbih(call: CallbackQuery):
    val = int(call.data.split("_")[1])
    new_val = val + 1 if val > 0 else 0
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"➕ سبّح ({new_val})", callback_data=f"ts_{new_val}")],
        [InlineKeyboardButton(text="🔄 تصفير", callback_data="ts_0")]
    ])
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

# --- لوحة التحكم والإذاعة ---

@dp.message(Command("admin"))
async def admin_cmd(msg: Message):
    if msg.from_user.id != OWNER_ID: return
    count = db.table("users").select("user_id", count="exact").execute().count
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 إذاعة رسالة", callback_data="start_bc")]])
    await msg.answer(f"🔐 **لوحة الإدارة**\n\nعدد المستخدمين: {count}", reply_markup=kb)

@dp.callback_query(F.data == "start_bc")
async def bc_step1(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.message.answer("📥 أرسل الآن الرسالة التي تريد إذاعتها (نص، صورة، إلخ):")
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def bc_step2(msg: Message, state: FSMContext):
    await state.clear()
    users = db.table("users").select("user_id").execute().data
    success, fail = 0, 0
    await msg.answer("⏳ بدأت عملية الإذاعة...")
    
    for u in users:
        try:
            await msg.copy_to(u['user_id'])
            success += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    
    await msg.answer(f"✅ تم الانتهاء:\nتم الإرسال لـ: {success}\nفشل الإرسال لـ: {fail}")

# --- التشغيل ---

async def main():
    logging.basicConfig(level=logging.INFO)
    await fetch_azkar()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

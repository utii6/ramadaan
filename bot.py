import os, random, logging, asyncio, aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from supabase import create_client, Client

# --- الإعدادات الأساسية ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CHANNEL_ID = "@qd3qd" # استبدله بيوزر قناتك الفعلي

AZKAR_URL = "https://raw.githubusercontent.com/nawafalqari/azkar-api/main/azkar.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ALL_AZKAR = {}

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()

# --- وظائف البيانات والتحقق ---

async def fetch_azkar():
    global ALL_AZKAR
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(AZKAR_URL) as r:
                if r.status == 200: ALL_AZKAR = await r.json()
        except Exception: pass

async def is_subbed(user_id):
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return m.status in ["member", "administrator", "creator"]
    except Exception: return True

def get_rank(count):
    if count < 100: return "🌱 ذاكر مبتدئ"
    if count < 500: return "✨ مستغفر مداوم"
    if count < 1000: return "📿 محب للذكر"
    return "🌟 من الذاكرين الله كثيراً"

# --- لوحات المفاتيح ---

def main_reply_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="📖 الأذكار الشاملة"), b.button(text="📿 السبحة الإلكترونية")
    b.button(text="📊 إحصائياتي"), b.button(text="⚙️ الإعدادات")
    b.button(text="🤝 صدقة جارية")
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

# --- المعالجات الرئيسية (Handlers) ---

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    user_id = msg.from_user.id
    if not await is_subbed(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 اشترك في القناة", url=f"t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="✅ تم الاشتراك", callback_data="check_sub")]
        ])
        return await msg.answer("✨ **أهلاً بك في بوت الأذكار**\n\nعذراً، يجب الاشتراك في القناة أولاً:", reply_markup=kb)

    # فحص المستخدم في القاعدة
    res = db.table("users").select("*").eq("user_id", user_id).execute()
    if not res.data:
        db.table("users").insert({"user_id": user_id, "username": msg.from_user.username, "full_name": msg.from_user.full_name}).execute()
        total_users = db.table("users").select("user_id", count="exact").execute().count
        await bot.send_message(OWNER_ID, f"🔔 **مشترك جديد**\n\nالاسم: {msg.from_user.full_name}\nالعدد الكلي: {total_users}")
    else:
        db.table("users").update({"username": msg.from_user.username, "full_name": msg.from_user.full_name}).eq("user_id", user_id).execute()

    welcome = f"✨ **مرحباً بك يا {msg.from_user.first_name}**"
    if user_id == OWNER_ID: welcome = "👑 **أهلاً بك يا مطوري العزيز**"
    await msg.answer(welcome, reply_markup=main_reply_kb())

@dp.message(F.text == "📖 الأذكار الشاملة")
async def show_cats(msg: Message):
    await msg.answer("🗂 **اختر التصنيف:**", reply_markup=azkar_cats_kb())

@dp.message(F.text == "📿 السبحة الإلكترونية")
async def tasbih_start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سبّح (0)", callback_data="ts_1")],
        [InlineKeyboardButton(text="🔄 تصفير", callback_data="ts_0")]
    ])
    await msg.answer("📿 **السبحة الإلكترونية**\n\nاضغط للبدء بالتسبيح:", reply_markup=kb)

@dp.message(F.text == "📊 إحصائياتي")
async def my_stats(msg: Message):
    res = db.table("users").select("total_reads").eq("user_id", msg.from_user.id).single().execute()
    count = res.data.get('total_reads', 0) if res.data else 0
    await msg.answer(f"━━━━━━━━━━━━\n👤 **ملف العبادة**\n\n✨ الأذكار المقروءة: `{count}`\n🏅 الرتبة: {get_rank(count)}\n━━━━━━━━━━━━")

@dp.message(F.text == "⚙️ الإعدادات")
async def settings(msg: Message):
    res = db.table("users").select("notifications_enabled").eq("user_id", msg.from_user.id).single().execute()
    status = res.data.get('notifications_enabled', True)
    btn_text = "🔕 إيقاف التنبيهات" if status else "🔔 تفعيل التنبيهات"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn_text, callback_data="toggle_notif")]])
    await msg.answer(f"⚙️ **إعدادات التنبيهات**\nالحالة: {'✅ مفعلة' if status else '❌ معطلة'}", reply_markup=kb)

@dp.message(F.text == "🤝 صدقة جارية")
async def share_bot(msg: Message):
    # زر المشاركة الشفاف (Switch Inline Query)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 مشاركة مع صديق", switch_inline_query="انصحك بهذا البوت الرائع للأذكار ✨")]
    ])
    await msg.answer(
        "✨ **ساهم في نشر الخير**\n\nشارك البوت مع أصدقائك ليكون لك صدقة جارية:\nhttps://t.me/RiRbBot",
        reply_markup=kb
    )

# --- معالجة الـ Callback Queries ---

@dp.callback_query(F.data.startswith("ts_"))
async def handle_ts(call: CallbackQuery):
    val = int(call.data.split("_")[1])
    new_val = val + 1 if val > 0 else 0
    if val > 0: # تحديث القاعدة عند التسبيح
        db.rpc('increment_reads', {'u_id': call.from_user.id}).execute()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"➕ سبّح ({new_val})", callback_data=f"ts_{new_val}")],
        [InlineKeyboardButton(text="🔄 تصفير", callback_data="ts_0")]
    ])
    await call.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query(F.data.startswith("az_"))
async def send_zekr(call: CallbackQuery):
    cat = call.data.split("_")[1]
    if not ALL_AZKAR: await fetch_azkar()
    item = random.choice(ALL_AZKAR.get(cat, [{"content": "ذكر الله حياة القلوب"}]))
    txt = item.get("content") or item.get("zekr")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ذكر آخر", callback_data=call.data)],
        [InlineKeyboardButton(text="✅ تمت القراءة", callback_data="done_read")]
    ])
    await call.message.edit_text(f"✨ **{cat}**\n\n{txt}", reply_markup=kb)

@dp.callback_query(F.data == "done_read")
async def done_r(call: CallbackQuery):
    db.rpc('increment_reads', {'u_id': call.from_user.id}).execute()
    await call.answer("تقبل الله منك! ✨")

@dp.callback_query(F.data == "toggle_notif")
async def toggle(call: CallbackQuery):
    res = db.table("users").select("notifications_enabled").eq("user_id", call.from_user.id).single().execute()
    new_s = not res.data.get('notifications_enabled', True)
    db.table("users").update({"notifications_enabled": new_s}).eq("user_id", call.from_user.id).execute()
    await call.message.edit_text(f"⚙️ تم التحديث! الحالة الآن: {'✅ مفعلة' if new_s else '❌ معطلة'}")

# --- الإدارة (Admin) ---

@dp.message(Command("admin"))
async def admin_panel(msg: Message):
    if msg.from_user.id == OWNER_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 إذاعة عامة", callback_data="start_bc")]])
        await msg.answer("🔒 لوحة التحكم", reply_markup=kb)

@dp.callback_query(F.data == "start_bc")
async def start_bc(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.message.answer("أرسل رسالة الإذاعة الآن:")

@dp.message(AdminStates.waiting_for_broadcast)
async def do_bc(msg: Message, state: FSMContext):
    await state.clear()
    users = db.table("users").select("user_id").execute().data
    s, f = 0, 0
    for u in users:
        try:
            await msg.copy_to(u['user_id'])
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await msg.answer(f"✅ انتهى الإرسال\nنجاح: {s} | فشل: {f}")

# --- الإقلاع ---

async def main():
    logging.basicConfig(level=logging.INFO)
    await fetch_azkar()
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

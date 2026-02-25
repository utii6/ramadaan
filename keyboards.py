from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📿 ذكر الآن", callback_data="send_now")
        ],
        [
            InlineKeyboardButton(text="⏱ تغيير الجدولة", callback_data="change_schedule")
        ]
    ])

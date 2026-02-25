from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from database import get_users, get_schedule
from utils import fetch_zekr

scheduler = AsyncIOScheduler()

def start_scheduler(bot: Bot):

    async def send_scheduled():
        users = get_users()
        for user_id in users:
            try:
                zekr = await fetch_zekr()
                await bot.send_message(user_id, zekr)
            except:
                pass

    scheduler.add_job(send_scheduled, "interval", hours=6)
    scheduler.start()

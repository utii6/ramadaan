import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
AZKAR_API_URL = os.getenv("AZKAR_API_URL")

DEFAULT_SCHEDULE_HOURS = 6

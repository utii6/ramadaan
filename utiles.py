import aiohttp
from config import AZKAR_API_URL

async def fetch_zekr():
    async with aiohttp.ClientSession() as session:
        async with session.get(AZKAR_API_URL) as response:
            data = await response.json()
            return data.get("content", "سبحان الله وبحمده")

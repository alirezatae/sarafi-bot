import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is not set (comma-separated)")

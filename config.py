import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not ADMIN_CHAT_ID:
    raise RuntimeError("ADMIN_CHAT_ID is not set")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

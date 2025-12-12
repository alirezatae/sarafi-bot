import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
]


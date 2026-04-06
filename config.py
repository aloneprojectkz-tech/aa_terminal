import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin Telegram IDs (comma-separated in env, e.g. "123456,789012")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:KdmIrPbMUiQJxjKrMPbgYooAaJFlCkLW@maglev.proxy.rlwy.net:46309/railway"
)

MAIL_TM_BASE = "https://api.mail.tm"

# How often (seconds) to poll mailboxes for new messages
POLL_INTERVAL = 30

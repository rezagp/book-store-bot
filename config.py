import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PURCHASE_TOKEN = os.getenv("PURCHASE_TOKEN")
BALE_BASE_URL = os.getenv("BALE_BASE_URL")
BALE_BASE_FILE_URL = os.getenv("BALE_BASE_FILE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
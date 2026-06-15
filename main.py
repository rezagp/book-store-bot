import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)
import logging
from telegram.ext import Application
from config import BOT_TOKEN, BALE_BASE_URL, BALE_BASE_FILE_URL
from core.bot_setup import register_handlers
from database.db_manager import upgrade_database

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def post_init(application):
    await upgrade_database()

def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .base_url(BALE_BASE_URL)
        .base_file_url(BALE_BASE_FILE_URL)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    register_handlers(application=application)

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()

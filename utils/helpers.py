import logging
from telegram.ext import ContextTypes
import traceback
import html
import pytz
import jdatetime

logger = logging.getLogger(__name__)

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    message_id = job.data['message_id']
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Error deleting message automatically: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    error_message = (
        f"🚨 *خطای پیش‌بینی نشده در ربات:*\n\n"
        f"{html.escape(tb_string[:3500])}"
    )

def convert_to_iran_jalali(utc_datetime):
    if utc_datetime.tzinfo is None:
        utc_datetime = pytz.utc.localize(utc_datetime)
    
    # تبدیل به منطقه زمانی ایران
    tehran_tz = pytz.timezone('Asia/Tehran')
    iran_time = utc_datetime.astimezone(tehran_tz)
    
    # تبدیل به تاریخ و زمان شمسی
    jalali_time = jdatetime.datetime.fromgregorian(datetime=iran_time)
    
    # خروجی به فرمت دلخواه (مثلاً: 1403/08/25 14:30)
    return jalali_time.strftime("%Y/%m/%d %H:%M")
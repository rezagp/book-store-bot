import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.helpers import delete_message_job
from database.db_manager import (
    generate_temp_download_link, 
    record_sale, 
)
from utils.keyboards import (
    download_file_keyboard
)

logger = logging.getLogger(__name__)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("invoice_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="خطا در پردازش فاکتور.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment_info = update.message.successful_payment
    payload = payment_info.invoice_payload
    user_id = update.message.from_user.id
    
    if payload.startswith("invoice_"):
        parts = payload.split("_")
        invoice_id = parts[1]
        book_id = parts[2]
        
        await record_sale(
            invoice_id = invoice_id,
            user_id = update.effective_user.id,
            amount = update.message.successful_payment.total_amount,
            currency = update.message.successful_payment.currency,
        )

        token = await generate_temp_download_link(user_id, book_id)
        bot_username = context.bot.username
        download_link = f"https://ble.ir/{bot_username}?start=dl_{token}"
        
        # ذخیره پیام در یک متغیر (sent_message)
        sent_message = await update.message.reply_text(
            "✅ پرداخت شما با موفقیت انجام شد!\n\n"
            "برای دریافت فایل، روی دکمه زیر کلیک کنید. در صورت کار نکردن دکمه، می‌توانید از لینک اختصاصی زیر استفاده کنید:\n"
            f"{download_link}\n\n"
            "⚠️ *توجه:* این لینک تنها برای *۱ ساعت* معتبر است و فقط *۲ بار* قابلیت استفاده دارد.",
            parse_mode='Markdown',
            reply_markup=download_file_keyboard(download_link)
        )

        # اضافه کردن زمان‌بندی حذف پیام برای 3600 ثانیه (یک ساعت) بعد
        if context.job_queue:
            context.job_queue.run_once(
                delete_message_job,
                when=3600,
                chat_id=user_id,
                data={'message_id': sent_message.message_id}
            )
        else:
            logger.warning("توجه: JobQueue فعال نیست و پیام حذف نخواهد شد. apscheduler را نصب کنید.")
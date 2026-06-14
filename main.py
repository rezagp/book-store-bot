import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)
import logging
import traceback
import html
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, PreCheckoutQueryHandler
from config import BOT_TOKEN, BALE_BASE_URL, PURCHASE_TOKEN, BALE_BASE_FILE_URL, ADMIN_ID
from database.db_manager import (
    add_user, 
    get_categories, 
    get_books_by_category, 
    get_book_by_id, search_books, 
    create_purchase_invoice, 
    generate_temp_download_link, 
    validate_download_token, 
    record_sale, 
    upgrade_database,
    check_is_admin
)
from utils.keyboards import (
    get_categories_keyboard, 
    get_books_keyboard, 
    download_file_keyboard
)
from handlers.admin_handlers import (
    admin_panel_handler, 
    admin_reply_button_handler,
    add_category_handler, 
    add_book_handler, 
    bulk_upload_handler, 
    statistics_handler, 
    admin_back_to_menu, 
    edit_category_conv, 
    edit_book_conv, 
    admin_exit_panel_handler, 
    delete_category_conv, 
    delete_book_conv, 
    buyers_pagination_handler, 
    show_buyers_pagination_handler, 
    buyers_pagination_back_handler,
    manage_admins_menu_handler,
    show_remove_admin_handler,
    remove_admin_action_handler,
    show_admins_list_handler,
    add_admin_conv
)

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    message_id = job.data['message_id']
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Error deleting message automatically: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await add_user(user.id, user.username, user.full_name)

    is_admin = await check_is_admin(user.id, ADMIN_ID)
    if is_admin and update.message:
        admin_keyboard = ReplyKeyboardMarkup([[KeyboardButton("ورود به پنل ادمین")]], resize_keyboard=True)
        await update.message.reply_text("شما ادمین هستید. دکمه پنل در پایین صفحه در دسترس است.", reply_markup=admin_keyboard)

    # دریافت دسته‌بندی‌ها از دیتابیس
    categories = await get_categories()

    # بررسی لینک دانلود
    if context.args and context.args[0].startswith("dl_"):
        token = context.args[0].replace("dl_", "")
        processing_msg = await update.message.reply_text("⏳ در حال بررسی لینک دانلود شما...")
        
        # اعتبارسنجی توکن در دیتابیس
        validation = await validate_download_token(token)
        
        if validation["status"] == "error":
            await processing_msg.edit_text(validation["message"])
        else:
            book_id = validation["book_id"]
            book = await get_book_by_id(book_id)
            
            if book and "file_link" in book:
                await processing_msg.edit_text(f"✅ لینک تایید شد. در حال آماده‌سازی کتاب: *{book['title']}* ...", parse_mode="Markdown")
                
                try:
                    success_msg = f"📚 نام کتاب: {book['title']}\n\n📥 لینک دانلود:\n{book['file_link']}\n\n@MEDBookbot\n\n⚠️ این پیام برای امنیت بیشتر، یک ساعت دیگر به صورت خودکار حذف خواهد شد."
                    sent_message = await context.bot.send_message(
                        chat_id=user.id,
                        text=success_msg,
                        disable_web_page_preview=True
                    )
                    await processing_msg.delete()

                    # زمان‌بندی حذف پیام برای 3600 ثانیه (یک ساعت) بعد
                    if context.job_queue:
                        context.job_queue.run_once(
                            delete_message_job,
                            when=3600,
                            chat_id=user.id,
                            data={'message_id': sent_message.message_id}
                        )
                except Exception as e:
                    await processing_msg.edit_text(f"❌ متاسفانه در ارسال فایل مشکلی از سمت سرور پیش آمد. لطفا به پشتیبانی اطلاع دهید.")
            else:
                await processing_msg.edit_text("❌ متاسفانه فایل این کتاب در دیتابیس یافت نشد.")
        
        # --- نمایش منوی دسته‌بندی بدون پیام سلام ---
        categories_text = "📚 برای مشاهده و خرید سایر کتاب‌ها، می‌توانید از دسته‌بندی‌های زیر استفاده کنید:"
        reply_markup = get_categories_keyboard(categories)
        await update.message.reply_text(text=categories_text, reply_markup=reply_markup)
        
        return

    reply_markup = get_categories_keyboard(categories)
    welcome_text = "سلام! به MEDBookbot خوش آمدید 📚\nلطفاً یک دسته‌بندی را انتخاب کنید یا نام کتاب را جستجو کنید:"
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_cats":
        await start_command(update, context)
        
    elif data.startswith("cat_"):
        category_name = data.split("cat_")[1]
        books = await get_books_by_category(category_name)
        
        if not books:
            await query.edit_message_text(f"در حال حاضر کتابی در {category_name} وجود ندارد.", 
                                          reply_markup=get_categories_keyboard(await get_categories()))
            return
        
        msg = f"*کتاب‌های بخش {category_name}:*\n\n"

        for book in books:
            msg += f"- {book["title"]}\n"

        reply_markup = get_books_keyboard(books)
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    elif data.startswith("book_"):
        book_id = data.split("book_")[1]
        book = await get_book_by_id(book_id)
        
        if book:
            from utils.keyboards import get_book_detail_keyboard
            
            price = int(book.get('price', 0))
            discount_percent = int(book.get('discount_percent', 0))
            
            # محاسبه مبلغ با تخفیف
            if discount_percent > 0:
                final_price = int(price * (1 - discount_percent / 100))
                formatted_price = f"{price:,}"
                strikethrough_price = "".join([char + '\u0336' if char != ',' else char for char in formatted_price])
                lrm = '\u200E'
                price_text = f"{lrm}{strikethrough_price}{lrm} {final_price:,} تومان ({discount_percent}٪ تخفیف)"
            else:
                final_price = price
                
                price_text = f"{price:,} تومان"
            
            text = (
                f"📖 *نام کتاب:* {html.escape(book['title'])}\n\n"
                f"💰 *مبلغ قابل پرداخت:* {price_text}\n\n"
                f"جهت پرداخت و دریافت لینک دانلود موقت، روی دکمه زیر کلیک کنید."
            )
            
            reply_markup = get_book_detail_keyboard(book_id)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.answer("خطا: کتاب مورد نظر یافت نشد!", show_alert=True)
            
    elif data.startswith("pay_") or data.startswith("buy_"):
        prefix = "pay_" if data.startswith("pay_") else "buy_"
        book_id = data.split(prefix)[1]
        
        user_id = query.from_user.id
        book = await get_book_by_id(book_id)
        
        if not book:
            await query.answer("خطا: کتاب مورد نظر یافت نشد!", show_alert=True)
            return
            
        price = int(book.get('price', 0))
        discount_percent = int(book.get('discount_percent', 0))
        
        # محاسبه مبلغ نهایی برای ارسال به درگاه
        if discount_percent > 0:
            final_price = int(price * (1 - discount_percent / 100))
        else:
            final_price = price
            
        invoice_id = await create_purchase_invoice(user_id, book_id, final_price)
        
        title = f"خرید فایل: {book['title'][:20]}" # محدود کردن طول تایتل برای امنیت تلگرام
        description = "پس از پرداخت، لینک دانلود اختصاصی برای شما ارسال می‌شود."
        payload = f"invoice_{invoice_id}_{book_id}" 
        provider_token = PURCHASE_TOKEN
        currency = "IRR" 
        
        price_in_rial = final_price * 10 
        prices = [LabeledPrice("قیمت کتاب", price_in_rial)]
        
        await context.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=provider_token,
            currency=currency,
            prices=prices
        )

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

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text
    books = await search_books(keyword)
    
    if not books:
        await update.message.reply_text("متاسفانه کتابی با این کلیدواژه پیدا نشد...")
        return
        
    response = f"*{len(books)} کتاب یافت شد:*\n\n"
    keyboard = []
    
    for book in books:
        book_id = str(book['_id'])
        original_price = book.get('price', 0)
        discount_percent = book.get('discount_percent', 0)
        
        # بررسی و اعمال منطق تخفیف
        if discount_percent > 0:
            discounted_price = int(original_price * (1 - discount_percent / 100))
            # ایجاد افکت خط‌خورده روی قیمت اصلی (به همراه جداکننده هزارگان)
            formatted_original = f"{original_price:,}"
            strikethrough_price = ''.join([c + '\u0336' for c in formatted_original])
            lrm = '\u200E'
            price_text = f"{lrm}{strikethrough_price}{lrm} {discounted_price:,} تومان \u200E(٪{discount_percent} تخفیف)"
        else:
            price_text = f"{original_price:,} تومان"

        response += f"📖 {book['title']}\n💰 قیمت: {price_text}\n\n"
        keyboard.append([InlineKeyboardButton(f"🛒 خرید {book['title']}", callback_data=f"buy_{book_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
        
    await update.message.reply_text(
        text=response,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    error_message = (
        f"🚨 *خطای پیش‌بینی نشده در ربات:*\n\n"
        f"{html.escape(tb_string[:3500])}"
    )
    
async def wrong_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لطفا از منوهای ربات استفاده کنید. ارسال فایل در اینجا مجاز نیست.")

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

    application.add_handler(CommandHandler("start", start_command))

    # هندلرهای ادمین
    application.add_handler(admin_panel_handler)
    application.add_handler(admin_reply_button_handler)
    application.add_handler(manage_admins_menu_handler)
    application.add_handler(show_remove_admin_handler)
    application.add_handler(remove_admin_action_handler)
    application.add_handler(show_admins_list_handler)
    application.add_handler(add_admin_conv)
    application.add_handler(add_category_handler)
    application.add_handler(add_book_handler)
    application.add_handler(bulk_upload_handler)
    application.add_handler(statistics_handler)
    application.add_handler(admin_back_to_menu)
    application.add_handler(edit_category_conv)
    application.add_handler(delete_category_conv)
    application.add_handler(edit_book_conv)
    application.add_handler(delete_book_conv)
    application.add_handler(admin_exit_panel_handler)
    application.add_handler(show_buyers_pagination_handler)
    application.add_handler(buyers_pagination_handler)
    application.add_handler(buyers_pagination_back_handler)

    # هندلرهای عمومی
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, wrong_file_handler))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    application.add_error_handler(error_handler)

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()

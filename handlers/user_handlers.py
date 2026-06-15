import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from config import ADMIN_ID, PURCHASE_TOKEN
from utils.helpers import delete_message_job
from database.db_manager import (
    add_user, 
    get_categories, 
    get_books_by_category, 
    get_book_by_id, search_books, 
    create_purchase_invoice, 
    validate_download_token, 
    check_is_admin,
    get_book_by_short_id
)
from utils.keyboards import (
    get_categories_keyboard, 
    get_books_keyboard, 
)

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await add_user(user.id, user.username, user.full_name)

    is_admin = await check_is_admin(user.id, ADMIN_ID)
    if is_admin and update.message:
        admin_keyboard = ReplyKeyboardMarkup([[KeyboardButton("ورود به پنل ادمین")]], resize_keyboard=True)
        await update.message.reply_text("شما ادمین هستید. دکمه پنل در پایین صفحه در دسترس است.", reply_markup=admin_keyboard)

    # دریافت دسته‌بندی‌ها از دیتابیس
    categories = await get_categories()

    # بخش بررسی ورودی‌های استارت (دیپ‌لینک‌ها)
    if context.args:
        arg = context.args[0]
        
        # ۱. بررسی لینک دانلود موقت (dl_)
        if arg.startswith("dl_"):
            token = arg.replace("dl_", "")
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
            
            # نمایش منوی دسته‌بندی بدون پیام سلام
            categories_text = "📚 برای مشاهده و خرید سایر کتاب‌ها، می‌توانید از دسته‌بندی‌های زیر استفاده کنید:"
            reply_markup = get_categories_keyboard(categories)
            await update.message.reply_text(text=categories_text, reply_markup=reply_markup)
            return

        # ۲. بررسی لینک اختصاصی معرفی کتاب (bk_)
        elif arg.startswith("bk_"):
            book = await get_book_by_short_id(arg)
            
            if book:
                from utils.keyboards import get_book_detail_keyboard
                
                price = int(book.get('price', 0))
                discount_percent = int(book.get('discount_percent', 0))
                
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
                
                reply_markup = get_book_detail_keyboard(str(book['_id']))
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            else:
                await update.message.reply_text("❌ متاسفانه این کتاب یافت نشد یا از سیستم حذف شده است.")
                # اینجا عمداً return نذاشتم تا اگر لینک خراب بود، پایین‌تر بره و منوی اصلی ربات رو به کاربر نشون بده

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

async def wrong_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لطفا از منوهای ربات استفاده کنید. ارسال فایل در اینجا مجاز نیست.")
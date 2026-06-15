import os
import pandas as pd
import re
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from handlers.admin.admin_core import cancel_admin
from utils.keyboards import admin_main_keyboard
from database.db_manager import (
    add_categories, 
    add_book, 
    get_categories, 
    search_books_by_title_for_admin, 
    update_book_field, 
    delete_book_from_db, 
    check_is_admin, 
    get_book_by_id
)

# Add New Book
WAITING_FOR_BOOK_CAT, WAITING_FOR_BOOK_TITLE, WAITING_FOR_BOOK_PRICE, WAITING_FOR_BOOK_DISCOUNT, WAITING_FOR_BOOK_FILE = range(2, 7)

async def ask_book_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # استفاده از تابع استاندارد به جای ایمپورت مستقیم کالکشن
    categories = await get_categories()
    
    if not categories:
        await query.edit_message_text("هیچ دسته‌بندی وجود ندارد! اول دسته‌بندی بسازید.")
        return ConversationHandler.END

    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat["name"], callback_data=f"selcat_{cat['name']}")])
    
    await query.edit_message_text("دسته بندی این کتاب را انتخاب کنید:\n(برای لغو /cancel را بفرستید)", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_FOR_BOOK_CAT

async def ask_book_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_cat = query.data.split("selcat_")[1]
    context.user_data['new_book_cat'] = selected_cat
    
    await query.edit_message_text(f"دسته {selected_cat} انتخاب شد.\n\nنام کتاب را وارد کنید (می‌توانید فارسی و انگلیسی را با هم بنویسید برای جستجوی بهتر):\n(برای لغو /cancel را بفرستید)")
    return WAITING_FOR_BOOK_TITLE

async def ask_book_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_book_title'] = update.message.text
    await update.message.reply_text("مبلغ کتاب را به تومان وارد کنید:\nمثال: 39000 یا 39,000 تومان")
    return WAITING_FOR_BOOK_PRICE

async def ask_book_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_raw = update.message.text
    clean_price = re.sub(r'\D', '', price_raw)
    
    if not clean_price:
        await update.message.reply_text("لطفاً قیمت را به درستی و شامل عدد وارد کنید!")
        return WAITING_FOR_BOOK_PRICE
        
    context.user_data['new_book_price'] = int(clean_price)
    print(context.user_data['new_book_price'])
    await update.message.reply_text("درصد تخفیف را وارد کنید (فقط عدد).\nمثلاً برای ۲۰٪ تخفیف عدد 20 را وارد کنید.\n(اگر تخفیف ندارد عدد 0 را بفرستید):")
    return WAITING_FOR_BOOK_DISCOUNT

async def ask_book_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    discount_raw = update.message.text
    clean_discount = re.sub(r'\D', '', discount_raw)
    
    if not clean_discount:
        clean_discount = 0
        
    context.user_data['new_book_discount'] = int(clean_discount)
    await update.message.reply_text("عالی! حالا نام دقیق فایل کتاب (به همراه فرمت، مثلاً book.pdf) را ارسال کنید:")
    return WAITING_FOR_BOOK_FILE

async def save_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)

    raw_filename = update.message.text.strip()
    encoded_filename = urllib.parse.quote(raw_filename)
    file_link = f"https://dl.anatomypedia.ir/books/{encoded_filename}"
    
    # دریافت short_id از دیتابیس
    short_id = await add_book(
        category=context.user_data['new_book_cat'],
        title=context.user_data['new_book_title'],
        price=context.user_data['new_book_price'],
        discount_percent=context.user_data['new_book_discount'],
        file_link=file_link
    )
    
    bot_username = context.bot.username
    deep_link = f"https://ble.ir/{bot_username}?start={short_id}"
    
    context.user_data.clear()
    await update.message.reply_text(
        text=f"✅ کتاب جدید با موفقیت ذخیره شد!\n\n🔗 لینک اختصاصی برای اشتراک‌گذاری در کانال:\n{deep_link}\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# Bulk Upload
WAITING_FOR_EXCEL, WAITING_FOR_ZIP = 6, 7

async def ask_bulk_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "📊 لطفاً فایل اکسل را ارسال کنید.\n\n"
        "دقت کنید فایل اکسل باید شامل ستون‌های زیر باشد:\n"
        "1. category (نام دسته)\n"
        "2. title (نام کتاب)\n"
        "3. price (قیمت)\n"
        "4. file_name (نام دقیق فایل در هاست)"
        "\n(برای لغو /cancel را بفرستید)"
    )
    await query.edit_message_text(text=text)
    return WAITING_FOR_EXCEL

async def process_bulk_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    excel_file = update.message.document
    os.makedirs("temp", exist_ok=True)
    
    msg = await update.message.reply_text("⏳ در حال دریافت و پردازش فایل اکسل...")
    
    new_file = await context.bot.get_file(excel_file.file_id)
    excel_path = os.path.join("temp", "data.xlsx")
    await new_file.download_to_drive(excel_path)
    
    try:
        df = pd.read_excel(excel_path)
        df['category'] = df['category'].ffill()

        success_count = 0

        for index, row in df.iterrows():
            category_name = str(row['category']).strip()
            await add_categories(category_name)
            
            price_str = str(row['price'])
            clean_price = re.sub(r'\D', '', price_str)
            final_price = int(clean_price) if clean_price else 0

            raw_filename = str(row.get('file_name', row.get('file_link', ''))).strip()
            encoded_filename = urllib.parse.quote(raw_filename)
            file_link = f"https://dl.anatomypedia.ir/books/{encoded_filename}"

            await add_book(
                category=category_name,
                title=str(row['title']),
                price=final_price,
                discount_percent=0,
                file_link=file_link
            )
            success_count += 1

        await msg.edit_text(f"✅ پردازش تمام شد!\nتعداد موفق: {success_count} کتاب به دیتابیس اضافه شد.")

    except Exception as e:
        await msg.edit_text(f"❌ خطایی رخ داد: {e}")
        
    finally:
        import shutil
        if os.path.exists("temp"):
            shutil.rmtree("temp")

    return ConversationHandler.END

# Edit Book
SEARCH_BOOK_EDIT, CHOOSE_FIELD_EDIT, ENTER_NEW_FIELD_VALUE = range(20, 23)

async def start_edit_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        return ConversationHandler.END
        
    await update.callback_query.edit_message_text(
        "لطفاً بخشی از نام کتابی که می‌خواهید ویرایش کنید را ارسال کنید:\n"
        "(برای لغو دستور /cancel را بفرستید)"
    )
    return SEARCH_BOOK_EDIT

async def search_book_for_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text
    books = await search_books_by_title_for_admin(search_text)
    
    if not books:
        await update.message.reply_text("کتابی با این نام یافت نشد. لطفاً نام دیگری امتحان کنید:")
        return SEARCH_BOOK_EDIT
        
    keyboard = []
    for book in books:
        book_id = str(book['_id'])
        keyboard.append([InlineKeyboardButton(book['title'], callback_data=f"editbook_{book_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("کتاب مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

    return CHOOSE_FIELD_EDIT

async def show_edit_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("editbook_"):
        book_id = query.data.split("_")[1]
        context.user_data['edit_book_id'] = book_id
    else:
        book_id = context.user_data.get('edit_book_id')

    keyboard = [
        [
            InlineKeyboardButton("📝 ویرایش نام", callback_data="edfield_title"),
            InlineKeyboardButton("💰 ویرایش قیمت", callback_data="edfield_price")
        ],
        [
            InlineKeyboardButton("🏷️ ویرایش تخفیف", callback_data="edfield_discount_percent"),
            InlineKeyboardButton("📁 ‌ویرایش دسته‌بندی", callback_data="edfield_category")
        ],
        [
            InlineKeyboardButton("🔗 ویرایش لینک کتاب", callback_data="edfield_file_link"),
            InlineKeyboardButton("📢 دریافت لینک اشتراک‌گذاری", callback_data="edfield_getlink"),
        ],
        [InlineKeyboardButton("✅ پایان ویرایش", callback_data="edfield_done")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "چه بخشی از این کتاب را می‌خواهید ویرایش کنید؟", 
        reply_markup=reply_markup
    )
    return CHOOSE_FIELD_EDIT

async def ask_for_new_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "edfield_done":
        await query.edit_message_text(
            text="✅ ویرایش کتاب به پایان رسید.\n\nلطفاً یک گزینه را انتخاب کنید:",
            reply_markup=admin_main_keyboard(is_super_admin=is_super)
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    if data == "edfield_getlink":
        book_id = context.user_data.get('edit_book_id')
        book = await get_book_by_id(book_id)
        bot_username = context.bot.username
        
        short_id = book.get('short_id')
        if not short_id:
            await query.answer("خطا: این کتاب شناسه کوتاه ندارد!", show_alert=True)
            return CHOOSE_FIELD_EDIT
            
        deep_link = f"https://ble.ir/{bot_username}?start={short_id}"
        
        await query.edit_message_text(
            f"🔗 لینک اختصاصی کتاب جهت معرفی در کانال:\n\n{deep_link}\n\n(برای کپی کردن، روی لینک کلیک کنید)",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_edit_menu")]])
        )
        return CHOOSE_FIELD_EDIT
    
    field_map = {
        "edfield_title": ("نام جدید", "title"),
        "edfield_price": ("قیمت جدید (به تومان)", "price"),
        "edfield_discount_percent": ("درصد تخفیف جدید (عدد)", "discount_percent"),
        "edfield_category": ("نام دسته‌بندی جدید", "category"),
        "edfield_file_link": ("نام فایل جدید (مثلاً book.pdf)", "file_link")
    }
    
    field_prompt, db_field = field_map[data]
    context.user_data['edit_db_field'] = db_field
    
    await query.edit_message_text(f"لطفاً {field_prompt} را ارسال کنید:")
    return ENTER_NEW_FIELD_VALUE

async def save_new_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    db_field = context.user_data.get('edit_db_field')
    book_id = context.user_data.get('edit_book_id')
    new_value = None
    
    if db_field == "file_link":
        if not update.message.text:
            await update.message.reply_text("لطفاً نام فایل را وارد کنید.")
            return ENTER_NEW_FIELD_VALUE
        raw_filename = update.message.text.strip()
        encoded_filename = urllib.parse.quote(raw_filename)
        new_value = f"https://dl.anatomypedia.ir/books/{encoded_filename}"
    elif db_field in ["price", "discount_percent"]:
        val_str = update.message.text
        clean_val = re.sub(r'\D', '', val_str)
        if not clean_val:
            await update.message.reply_text("لطفاً مقدار را به صورت عدد وارد کنید:")
            return ENTER_NEW_FIELD_VALUE
        new_value = int(clean_val)
    else:
        new_value = update.message.text
        
    # آپدیت دیتابیس
    await update_book_field(book_id, db_field, new_value)
    
    await update.message.reply_text(
        text="✅ فیلد با موفقیت آپدیت شد و از حالت ویرایش خارج شدید.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )
    context.user_data.clear()
    return ConversationHandler.END

# Delete Book
SEARCH_BOOK_DELETE, CHOOSE_FIELD_DELETE = range(40, 42)

async def start_delete_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        return ConversationHandler.END
        
    await update.callback_query.edit_message_text(
        "لطفاً بخشی از نام کتابی که می‌خواهید حذف کنید را ارسال کنید:\n"
        "(برای لغو دستور /cancel را بفرستید)"
    )
    return SEARCH_BOOK_DELETE

async def search_book_for_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text
    books = await search_books_by_title_for_admin(search_text)
    
    if not books:
        await update.message.reply_text("کتابی با این نام یافت نشد. لطفاً نام دیگری امتحان کنید:")
        return SEARCH_BOOK_EDIT
        
    keyboard = []
    for book in books:
        book_id = str(book['_id'])
        keyboard.append([InlineKeyboardButton(book['title'], callback_data=f"deletebook_{book_id}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("کتاب مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

    return CHOOSE_FIELD_DELETE

async def show_delete_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    query = update.callback_query
    await query.answer()
    
    # اگر از جستجو آمده باشد، دیتا با deletebook_ شروع می‌شود
    if query.data.startswith("deletebook_"):
        book_id = query.data.split("_")[1]
    else:
        # اگر از مرحله قبل برگشته باشد
        book_id = context.user_data.get('edit_book_id')
    print(book_id)
    await delete_book_from_db(book_id)
    
    # تغییر مهم: نمایش پیام موفقیت و بستن کامل کانوِرسِیشِن
    await query.edit_message_text(
        text="✅ کتاب با موفقیت حذف شد.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )
    
    # پاک کردن کش و پایان
    context.user_data.clear()
    return ConversationHandler.END

add_book_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_book_category, pattern="^admin_add_book$")],
    states={
        WAITING_FOR_BOOK_CAT: [CallbackQueryHandler(ask_book_title, pattern="^selcat_")],
        WAITING_FOR_BOOK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_book_price)],
        WAITING_FOR_BOOK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_book_discount)],
        WAITING_FOR_BOOK_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_book_file)],
        WAITING_FOR_BOOK_FILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_book)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_admin),
        CallbackQueryHandler(cancel_admin, pattern='^back_to_menu$')
    ]
)

bulk_upload_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_bulk_excel, pattern="^admin_bulk_upload$")],
    states={
        WAITING_FOR_EXCEL: [MessageHandler(filters.Document.ALL, process_bulk_excel)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_admin),
        CallbackQueryHandler(cancel_admin, pattern='^back_to_menu$')
    ]
)

edit_book_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_book, pattern='^admin_edit_book$')],
    states={
        SEARCH_BOOK_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_book_for_edit)],
        CHOOSE_FIELD_EDIT: [
            CallbackQueryHandler(show_edit_fields, pattern="^editbook_|^back_to_edit_menu$"),
            CallbackQueryHandler(ask_for_new_field_value, pattern="^edfield_")
        ],
        ENTER_NEW_FIELD_VALUE: [
            MessageHandler(filters.TEXT | filters.Document.ALL & ~filters.COMMAND, save_new_field_value)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
)

delete_book_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_delete_book, pattern='^admin_delete_book$')],
    states={
        SEARCH_BOOK_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_book_for_delete)],
        CHOOSE_FIELD_DELETE: [CallbackQueryHandler(show_delete_fields, pattern="^deletebook_|^back_to_delete_menu$")],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
)
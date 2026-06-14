import os
import pandas as pd
import re
import pytz
import jdatetime
from datetime import datetime
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from utils.keyboards import (
    admin_main_keyboard, 
    back_to_menu, 
    get_pagination_keyboard, 
    manage_admins_keyboard, 
    admins_list_for_delete_keyboard
)
from database.db_manager import (
    add_categories, 
    add_book, 
    calc_statistics, 
    get_categories, 
    update_category_name, 
    search_books_by_title_for_admin, 
    update_book_field, 
    delete_category_from_db, 
    delete_book_from_db, 
    get_unique_buyers, 
    check_is_admin, 
    make_user_admin, 
    remove_user_admin, 
    get_all_admins
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

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # بررسی ادمین بودن (از دیتابیس)
    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        await update.message.reply_text("⛔️ شما به این بخش دسترسی ندارید.")
        return

    is_super = (user_id == ADMIN_ID)
    await update.message.reply_text(
        "👨‍💻 به پنل مدیریت MEDBookbot خوش آمدید.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )

async def admin_panel_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # بررسی ادمین بودن
    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        # اگر یوزر عادی متن دکمه را فرستاد، هیچ اتفاقی نمی‌افتد و نادیده گرفته می‌شود
        return

    # اگر ادمین بود، همان تابع اصلی پنل را فراخوانی کن
    await admin_panel_command(update, context)

# Add New Category
WAITING_FOR_CATEGORY_NAME = 1

async def ask_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="نام دسته‌بندی جدید را وارد کنید:\n(برای لغو /cancel را بفرستید)"
    )
    return WAITING_FOR_CATEGORY_NAME

async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)

    category_name = update.message.text
    await add_categories(category_name)
    
    await update.message.reply_text(
        text=f"✅ دسته‌بندی «{category_name}» با موفقیت اضافه شد!\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )
    return ConversationHandler.END

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
    
    await add_book(
        category=context.user_data['new_book_cat'],
        title=context.user_data['new_book_title'],
        price=context.user_data['new_book_price'],
        discount_percent=context.user_data['new_book_discount'],
        file_link=file_link
    )
    
    context.user_data.clear()
    await update.message.reply_text(
        text="✅ کتاب جدید به همراه فایل با موفقیت در دیتابیس ذخیره شد!\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
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

async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    query = update.callback_query

    if query:
        await update.callback_query.edit_message_text(
        text="عملیات لغو شد.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
        )
    else:
        await update.message.reply_text(
        text="عملیات لغو شد.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
        )
    return ConversationHandler.END

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    get_calc_statistics = await calc_statistics()

    if get_calc_statistics['sales_agg']:
        total_revenue = get_calc_statistics['sales_agg'][0]['total_revenue']
    else:
        total_revenue = 0
        
    text = (
        "📊 *آمار کلی ربات شما:*\n\n"
        f"👥 تعداد کاربران: {get_calc_statistics['total_users']}\n"
        f"🗂 تعداد دسته‌بندی‌ها: {get_calc_statistics['total_categories']}\n"
        f"📚 تعداد کل کتاب‌ها: {get_calc_statistics['total_books']}\n"
        "〰️〰️〰️〰️〰️〰️\n"
        f"🛒 تعداد کل فروش‌ها: {get_calc_statistics['total_sales_count']}\n"
        f"💰 مجموع درآمد: {total_revenue:,} تومان\n"
    )
    
    await query.edit_message_text(
        text=text, parse_mode='MARKDOWN',
        reply_markup=back_to_menu()
    )

async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    query = update.callback_query

    await query.edit_message_text(
        text="👨‍💻 به پنل مدیریت MEDBookbot خوش آمدید.\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )

async def handle_exit_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("شما از پنل ادمین خارج شدید. 🚪")
    
    from main import start_command 
    await start_command(update, context)

# Edit Category
SELECT_CATEGORY_TO_EDIT, ENTER_NEW_CATEGORY_NAME = range(10, 12) # اعداد دلخواه که تداخل نداشته باشند
async def start_edit_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        return ConversationHandler.END
        
    categories = await get_categories()

    if not categories:
        await update.message.reply_text("هیچ دسته‌بندی‌ای برای ویرایش وجود ندارد.")
        return ConversationHandler.END

    # نمایش لیست دسته‌ها به صورت دکمه شیشه‌ای یا متن
    cats_text = "\n".join([f"- {cat['name']}" for cat in categories])
    await update.callback_query.edit_message_text(
        f"لیست دسته‌بندی‌های فعلی:\n{cats_text}\n\n"
        "لطفاً نام دسته‌ای که می‌خواهید ویرایش کنید را دقیقاً تایپ کنید:\n"
        "(برای لغو دستور /cancel را بفرستید)"
    )
    return SELECT_CATEGORY_TO_EDIT

async def receive_category_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    old_name = update.message.text
    context.user_data['old_category_name'] = old_name
    
    await update.message.reply_text(
        f"دسته '{old_name}' انتخاب شد. \n"
        "لطفاً نام جدید این دسته را ارسال کنید:"
    )
    return ENTER_NEW_CATEGORY_NAME

async def save_new_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text
    old_name = context.user_data.get('old_category_name')
    
    await update_category_name(old_name, new_name)
    
    await update.message.reply_text(f"✅ نام دسته از '{old_name}' به '{new_name}' تغییر یافت و تمام کتاب‌های مرتبط نیز آپدیت شدند.")
    context.user_data.clear()
    return ConversationHandler.END

# Delete Category
SELECT_CATEGORY_TO_DELETE = 30

async def start_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    is_admin = await check_is_admin(user_id, ADMIN_ID)
    if not is_admin:
        return ConversationHandler.END
        
    categories = await get_categories()
    
    if not categories:
        await update.message.reply_text("هیچ دسته‌بندی‌ای برای ویرایش وجود ندارد.")
        return ConversationHandler.END

    # نمایش لیست دسته‌ها به صورت دکمه شیشه‌ای یا متن
    cats_text = "\n".join([f"- {cat['name']}" for cat in categories])
    await update.callback_query.edit_message_text(
        f"لیست دسته‌بندی‌های فعلی:\n{cats_text}\n\n"
        "لطفاً نام دسته‌ای که می‌خواهید حذف کنید را دقیقاً تایپ کنید:\n"
        "(برای لغو دستور /cancel را بفرستید)"
    )
    return SELECT_CATEGORY_TO_DELETE

async def receive_category_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    cat_name = update.message.text

    await delete_category_from_db(cat_name)

    await update.message.reply_text(
        text=f"✅ دسته‌بندی {cat_name} حذف شد!\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )

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
            InlineKeyboardButton("🔗 ویرایش لینک کتاب", callback_data="edfield_file_link")
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

# Show Buyers list
async def show_buyers_page(update, context, page: int = 1, is_callback: bool = False):
    buyers, total_pages, total_count = await get_unique_buyers(page, limit=5)
    
    if total_count == 0:
        text = "نتیجه‌ای یافت نشد. تاکنون خرید موفقی ثبت نشده است."
        if is_callback:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"👥 *لیست خریداران (کل: {total_count} کاربر)*\n"
    text += f"📄 صفحه {page} از {total_pages}\n\n"
    
    for buyer in buyers:
        user_id = buyer.get('_id')
        
        # دریافت اطلاعات از داکیومنت جوین شده
        user_details = buyer.get('user_details', {})
        # اینجا از full_name استفاده می‌کنیم
        full_name = user_details.get('full_name', 'ناشناس')
        username = user_details.get('username')
        
        purchase_count = buyer.get('purchase_count', 0)
        total_spent = buyer.get('total_spent', 0)
        last_date = buyer.get('last_purchase_date')
        
        # فرمت‌بندی تاریخ
        if isinstance(last_date, datetime):
            # تبدیل تاریخ به فرمت خوانا (میلادی)
            last_date_str = last_date.strftime("%Y-%m-%d %H:%M")
        else:
            last_date_str = "نامشخص"
        
        text += f"👤 کاربر: *{full_name}*"
        if username:
            text += f" (@{username})\n"
        else:
            text += f" (ID: `{user_id}`)\n"
        
        jalali_date_str = convert_to_iran_jalali(buyer['last_purchase_date'])

        text += f"🛍️ تعداد خرید: {purchase_count} کتاب\n"
        text += f"💰 مجموع پرداخت: {total_spent:,} تومان\n"
        text += f"📅 آخرین خرید: {jalali_date_str}\n"
        text += "〰️〰️〰️〰️〰️〰️〰️〰️\n"

    # پیشوند دکمه‌ها باید دقیقاً همانی باشد که در CallbackQueryHandler تعریف کرده‌اید
    reply_markup = get_pagination_keyboard(page, total_pages, prefix="buyers_page_")

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def buyers_pagination_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "ignore":
        return
   
    # استخراج شماره صفحه از callback_data (مثلاً buyers_page_2)
    page = int(data.split("_")[2])
    await show_buyers_page(update, context, page=page, is_callback=True)

# --- مدیریت ادمین‌ها ---
WAITING_FOR_NEW_ADMIN_ID = 50

async def manage_admins_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.callback_query.edit_message_text(
        "👮‍♂️ بخش مدیریت ادمین‌ها\nیک گزینه را انتخاب کنید:",
        reply_markup=manage_admins_keyboard()
    )

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.callback_query.edit_message_text(
        "لطفاً **آی‌دی عددی (User ID)** کاربری که می‌خواهید ادمین شود را بفرستید:\n(کاربر باید قبلاً ربات را استارت زده باشد)\n\nبرای لغو /cancel را بفرستید."
    )
    return WAITING_FOR_NEW_ADMIN_ID

async def receive_new_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_admin_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("آی‌دی باید فقط شامل عدد باشد. دوباره تلاش کنید:")
        return WAITING_FOR_NEW_ADMIN_ID

    success = await make_user_admin(new_admin_id)
    if success:
        await update.message.reply_text("✅ کاربر با موفقیت به عنوان ادمین سطح ۲ ثبت شد.", reply_markup=admin_main_keyboard(is_super_admin=True))
    else:
        await update.message.reply_text("❌ کاربر در دیتابیس یافت نشد! ابتدا باید کاربر ربات را استارت بزند.", reply_markup=admin_main_keyboard(is_super_admin=True))
    return ConversationHandler.END

async def show_remove_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    admins = await get_all_admins()
    if not admins:
        await update.callback_query.edit_message_text("هیچ ادمین سطح دویی ثبت نشده است.", reply_markup=manage_admins_keyboard())
        return
    await update.callback_query.edit_message_text("روی نام کاربری که می‌خواهید از ادمینی حذف شود کلیک کنید:", reply_markup=admins_list_for_delete_keyboard(admins))

async def handle_remove_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    query = update.callback_query
    target_id = int(query.data.split("_")[1])
    await remove_user_admin(target_id)
    await query.answer("ادمین با موفقیت حذف شد", show_alert=True)
    await show_remove_admin_list(update, context) # رفرش لیست

async def show_admins_list_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    admins = await get_all_admins()
    if not admins:
        text = "هیچ ادمین سطح دویی ثبت نشده است."
    else:
        text = "📋 لیست ادمین‌های پشتیبان:\n\n"
        for a in admins:
            text += f"👤 {a.get('full_name', 'ناشناس')} (ID: `{a['user_id']}`)\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="manage_admins_menu")]]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Handlers
admin_panel_handler = CommandHandler("admin", admin_panel_command)
admin_reply_button_handler = MessageHandler(filters.Regex('^ورود به پنل ادمین$'), admin_panel_message_handler)

manage_admins_menu_handler = CallbackQueryHandler(manage_admins_menu_callback, pattern='^manage_admins_menu$')
show_remove_admin_handler = CallbackQueryHandler(show_remove_admin_list, pattern='^remove_admin_list$')
remove_admin_action_handler = CallbackQueryHandler(handle_remove_admin_action, pattern='^deladmin_')
show_admins_list_handler = CallbackQueryHandler(show_admins_list_only, pattern='^list_admins_only$')

add_admin_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_admin, pattern='^add_admin_start$')],
    states={
        WAITING_FOR_NEW_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_admin_id)],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
)

add_category_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_category_name, pattern="^admin_add_category$")],
    states={
        WAITING_FOR_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_category)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_admin),
        CallbackQueryHandler(cancel_admin, pattern='^back_to_menu$')
    ]
)

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

statistics_handler = CallbackQueryHandler(show_statistics, pattern='^admin_stats$')

admin_back_to_menu = CallbackQueryHandler(handle_back_to_menu, pattern='^back_to_menu$')

admin_exit_panel_handler = CallbackQueryHandler(handle_exit_panel, pattern='^admin_exit_panel$')

edit_category_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_category, pattern='^admin_edit_category$')],
    states={
        SELECT_CATEGORY_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category_to_edit)],
        ENTER_NEW_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_category_name)],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
)

delete_category_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_delete_category, pattern='^admin_delete_category$')],
    states={
        SELECT_CATEGORY_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category_to_delete)],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
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

show_buyers_pagination_handler = CallbackQueryHandler(show_buyers_page, pattern="^show_buyers_page$")
buyers_pagination_handler = CallbackQueryHandler(buyers_pagination_callback, pattern="^buyers_page_")
buyers_pagination_back_handler = CallbackQueryHandler(cancel_admin, pattern="^pagination_back_to_menu")
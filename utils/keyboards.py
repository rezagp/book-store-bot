from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def admin_main_keyboard(is_super_admin=False):
    keyboard = [
        [InlineKeyboardButton("📁 افزودن دسته‌بندی جدید", callback_data="admin_add_category")],
        [
            InlineKeyboardButton("⚙️ ویرایش دسته‌بندی", callback_data="admin_edit_category"),
            InlineKeyboardButton("🗑 حذف دسته‌بندی", callback_data="admin_delete_category"),
        ],
        [InlineKeyboardButton("📚 افزودن کتاب جدید", callback_data="admin_add_book")],
        [
            InlineKeyboardButton("⚙️ ویرایش کتاب", callback_data="admin_edit_book"),
            InlineKeyboardButton("🗑 حذف کتاب", callback_data="admin_delete_book"),
        ],
        [InlineKeyboardButton("📦 آپلود گروهی (اکسل)", callback_data="admin_bulk_upload")],
        [InlineKeyboardButton("👥 لیست خریدارها", callback_data="show_buyers_page")],
        [InlineKeyboardButton("📊 آمار فروش", callback_data="admin_stats")],
    ]
    
    if is_super_admin:
         keyboard.append([InlineKeyboardButton("👮‍♂️ مدیریت ادمین‌ها", callback_data="manage_admins_menu")])
         
    keyboard.append([InlineKeyboardButton("❌ خروج از پنل ادمین", callback_data="admin_exit_panel")])
    return InlineKeyboardMarkup(keyboard)

def manage_admins_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin_start")],
        [InlineKeyboardButton("➖ حذف ادمین", callback_data="remove_admin_list")],
        [InlineKeyboardButton("📋 لیست ادمین‌ها", callback_data="list_admins_only")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admins_list_for_delete_keyboard(admins):
    keyboard = []
    for admin in admins:
        name = admin.get('full_name', 'بدون نام')
        uid = admin['user_id']
        keyboard.append([InlineKeyboardButton(f"❌ حذف: {name}", callback_data=f"deladmin_{uid}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_admins_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_categories_keyboard(categories):
    keyboard = []
    # برای چیدمان بهتر، دکمه‌ها رو دوتا دوتا در هر ردیف می‌چینیم
    row = []
    for cat in categories:
        # callback_data دیتایی هست که وقتی کاربر کلیک می‌کنه به ربات ارسال می‌شه
        row.append(InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['name']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: # اگر دکمه‌ای فرد مونده بود
        keyboard.append(row)
        
    return InlineKeyboardMarkup(keyboard)

def get_books_keyboard(books):
    keyboard = []
    for book in books:
        # آیدی دیتابیس کتاب رو در callback_data می‌ذاریم که بعدا بتونیم پیداش کنیم
        keyboard.append([InlineKeyboardButton(book['title'], callback_data=f"book_{str(book['_id'])}")])
    
    # دکمه برگشت
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به دسته‌بندی‌ها", callback_data="back_to_cats")])
    return InlineKeyboardMarkup(keyboard)

def download_file_keyboard(download_link):
    keyboard = [
            [InlineKeyboardButton("📥 دریافت فایل کتاب", url=download_link)]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_book_detail_keyboard(book_id):
    keyboard = [
        # فعلا یک دکمه شیشه‌ای ساده می‌سازیم تا بعدا درگاه را به آن متصل کنیم
        [InlineKeyboardButton("💳 خرید و دریافت فایل", callback_data=f"pay_{book_id}")],
        [InlineKeyboardButton("🔙 بازگشت به دسته‌بندی‌ها", callback_data="back_to_cats")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_menu():
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str = "buyers_page_"):
    buttons = []
    nav_buttons = []
    
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("➡️ قبلی", callback_data=f"{prefix}{current_page - 1}"))
        
    nav_buttons.append(InlineKeyboardButton(f"صفحه {current_page} از {total_pages}", callback_data="ignore"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("بعدی ⬅️", callback_data=f"{prefix}{current_page + 1}"))
        
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="pagination_back_to_menu")])
    return InlineKeyboardMarkup(buttons)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from utils.keyboards import admin_main_keyboard, back_to_menu
from database.db_manager import calc_statistics, check_is_admin, set_ad_text, get_ad_text, clear_ad_text

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

# Ads
WAITING_FOR_AD_TEXT = 100

async def show_ad_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    current_ad = await get_ad_text()
    ad_display = current_ad if current_ad else "هیچ تبلیغی فعال نیست ❌"
    
    text = f"📢 *تنظیمات تبلیغ انتهای پیام دانلود*\n\nمتن فعلی:\n{ad_display}\n\nچه کاری می‌خواهید انجام دهید؟"
    
    keyboard = [
        [InlineKeyboardButton("✍️ ثبت یا تغییر متن تبلیغ", callback_data="set_new_ad")],
    ]
    if current_ad:
        keyboard.append([InlineKeyboardButton("🗑 حذف تبلیغ فعلی", callback_data="delete_current_ad")])
        
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await clear_ad_text()
    await query.answer("✅ تبلیغ با موفقیت حذف شد.", show_alert=True)
    # بازگشت خودکار به منوی قبلی
    await show_ad_settings(update, context)

async def ask_for_ad_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "لطفاً متن تبلیغ خود را دقیقاً همانطور که می‌خواهید نمایش داده شود بفرستید:\n(می‌توانید از ایموجی هم استفاده کنید)\n\nبرای لغو /cancel را بفرستید."
    )
    return WAITING_FOR_AD_TEXT

async def save_new_ad_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_super = (user_id == ADMIN_ID)
    
    new_ad = update.message.text
    await set_ad_text(new_ad)
    
    await update.message.reply_text(
        "✅ تبلیغ جدید با موفقیت ذخیره شد و از این به بعد در انتهای پیام‌های دانلود نمایش داده می‌شود.",
        reply_markup=admin_main_keyboard(is_super_admin=is_super)
    )
    return ConversationHandler.END

# Handlers
admin_panel_handler = CommandHandler("admin", admin_panel_command)
admin_reply_button_handler = MessageHandler(filters.Regex('^ورود به پنل ادمین$'), admin_panel_message_handler)
statistics_handler = CallbackQueryHandler(show_statistics, pattern='^admin_stats$')
admin_back_to_menu = CallbackQueryHandler(handle_back_to_menu, pattern='^back_to_menu$')
admin_exit_panel_handler = CallbackQueryHandler(handle_exit_panel, pattern='^admin_exit_panel$')

ad_settings_menu_handler = CallbackQueryHandler(show_ad_settings, pattern='^admin_ad_settings$')
delete_ad_handler = CallbackQueryHandler(handle_delete_ad, pattern='^delete_current_ad$')

ad_setup_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_for_ad_text, pattern='^set_new_ad$')],
    states={
        WAITING_FOR_AD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_ad_text)],
    },
    fallbacks=[CommandHandler("cancel", cancel_admin)]
)
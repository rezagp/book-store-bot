from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from utils.keyboards import admin_main_keyboard, back_to_menu
from database.db_manager import calc_statistics, check_is_admin

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

admin_panel_handler = CommandHandler("admin", admin_panel_command)
admin_reply_button_handler = MessageHandler(filters.Regex('^ورود به پنل ادمین$'), admin_panel_message_handler)
statistics_handler = CallbackQueryHandler(show_statistics, pattern='^admin_stats$')
admin_back_to_menu = CallbackQueryHandler(handle_back_to_menu, pattern='^back_to_menu$')
admin_exit_panel_handler = CallbackQueryHandler(handle_exit_panel, pattern='^admin_exit_panel$')

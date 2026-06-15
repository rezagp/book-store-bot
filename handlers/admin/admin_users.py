from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from handlers.admin.admin_core import cancel_admin
from utils.helpers import convert_to_iran_jalali
from utils.keyboards import (
    admin_main_keyboard, 
    get_pagination_keyboard, 
    manage_admins_keyboard, 
    admins_list_for_delete_keyboard
)
from database.db_manager import (
    get_unique_buyers, 
    make_user_admin, 
    remove_user_admin, 
    get_all_admins
)

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

show_buyers_pagination_handler = CallbackQueryHandler(show_buyers_page, pattern="^show_buyers_page$")
buyers_pagination_handler = CallbackQueryHandler(buyers_pagination_callback, pattern="^buyers_page_")
buyers_pagination_back_handler = CallbackQueryHandler(cancel_admin, pattern="^pagination_back_to_menu")
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_ID
from handlers.admin.admin_core import cancel_admin
from utils.keyboards import admin_main_keyboard
from database.db_manager import (
    add_categories, 
    get_categories, 
    update_category_name, 
    delete_category_from_db, 
    check_is_admin, 
)


WAITING_FOR_CATEGORY_NAME = 1
SELECT_CATEGORY_TO_EDIT, ENTER_NEW_CATEGORY_NAME = range(10, 12)
SELECT_CATEGORY_TO_DELETE = 30

# Add New Category
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

# Edit Category
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
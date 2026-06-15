from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, PreCheckoutQueryHandler
from utils.helpers import error_handler
from handlers.user_handlers import start_command, wrong_file_handler, search_handler, button_handler
from handlers.payment_handlers import precheckout_callback, successful_payment_callback
from handlers.admin.admin_core import (
        admin_panel_handler, 
        admin_reply_button_handler,
        statistics_handler,
        admin_back_to_menu,
        admin_exit_panel_handler,
)
from handlers.admin.admin_cats import (
        add_category_handler,
        edit_category_conv,
        delete_category_conv, 
)
from handlers.admin.admin_books import (
        add_book_handler,
        bulk_upload_handler, 
        edit_book_conv, 
        delete_book_conv, 
)
from handlers.admin.admin_users import (
    buyers_pagination_handler, 
    show_buyers_pagination_handler, 
    buyers_pagination_back_handler,
    manage_admins_menu_handler,
    show_remove_admin_handler,
    remove_admin_action_handler,
    show_admins_list_handler,
    add_admin_conv
)
def register_handlers(application):
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
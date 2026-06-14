from database.connection import users_collection, categories_collection, books_collection, purchases_collection, links_collection
from bson import ObjectId
from datetime import datetime, timedelta, timezone
import uuid
import math

def get_now_utc():
    """تابع کمکی برای تولید زمان استاندارد و جلوگیری از تکرار کد"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def add_user(user_id: int, username: str, full_name: str):
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        await users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "role": "user",
            "joined_at": get_now_utc()
        })

async def add_categories(category_name):
    await categories_collection.update_one(
        {"name": category_name}, 
        {"$setOnInsert": {"name": category_name}}, 
        upsert=True
    )

async def add_book(category, title, price, discount_percent, file_link):
    book_data = {
        "category": category,
        "title": title,
        "price": price,
        "discount_percent": discount_percent,
        "file_link": file_link
    }
    await books_collection.insert_one(book_data)

async def get_categories():
    cursor = categories_collection.find({})
    return await cursor.to_list(length=None)

async def get_books_by_category(category_name: str):
    cursor = books_collection.find({"category": category_name})
    return await cursor.to_list(length=None)

async def search_books(keyword: str):
    # تقسیم کلمات کلیدی کاربر و حذف فاصله‌های اضافی
    words = [w.strip() for w in keyword.split() if w.strip()]
    
    if not words:
        return []
    
    # ساخت شرط‌های جستجو (رجکس) برای هر کلمه به صورت جداگانه
    regex_conditions = []
    for word in words:
        regex_conditions.append({"title": {"$regex": word, "$options": "i"}})
    
    # استفاده از عملگر $and برای یافتن کتاب‌هایی که تمام کلمات را دارند
    query = {"$and": regex_conditions} if len(regex_conditions) > 1 else regex_conditions[0]
    
    cursor = books_collection.find(query)
    return await cursor.to_list(length=None)

async def get_book_by_id(book_id: str):
    return await books_collection.find_one({"_id": ObjectId(book_id)})

async def create_purchase_invoice(user_id: int, book_id: str, amount: int):
    invoice = {
        "user_id": user_id,
        "book_id": book_id,
        "amount": amount,
        "status": "pending",
        "created_at": get_now_utc()
    }
    result = await purchases_collection.insert_one(invoice)
    return str(result.inserted_id)

async def generate_temp_download_link(user_id: int, book_id: str):
    token = str(uuid.uuid4()) # تولید یک رشته تصادفی یکتا
    
    link_data = {
        "token": token,
        "user_id": user_id,
        "book_id": book_id,
        "clicks_left": 2, # از ۲ شروع می‌شود و کم می‌شود
        "expires_at": get_now_utc() + timedelta(hours=1) # زمان فعلی + ۱ ساعت
    }
    await links_collection.insert_one(link_data)
    return token

async def validate_download_token(token: str):
    token_doc = await links_collection.find_one({"token": token})
    
    if not token_doc:
        return {"status": "error", "message": "❌ لینک دانلود نامعتبر است یا وجود ندارد."}
    
    now_utc = get_now_utc()
    expires_at = token_doc.get("expires_at")
    
    # ۱. بررسی انقضای زمان
    if not expires_at or now_utc > expires_at:
        return {"status": "error", "message": "❌ زمان لینک دانلود شما (۱ ساعت) به پایان رسیده و منقضی شده است."}
    
    # ۲. بررسی تعداد کلیک‌های باقی‌مانده
    clicks_left = token_doc.get("clicks_left", 0)
    if clicks_left <= 0:
        return {"status": "error", "message": "❌ شما بیش از حد مجاز (۲ بار) از این لینک استفاده کرده‌اید."}
    
    # در صورت معتبر بودن، یک واحد از کلیک‌ها کم می‌کنیم
    await links_collection.update_one(
        {"_id": token_doc["_id"]},
        {"$inc": {"clicks_left": -1}}
    )
    
    return {"status": "success", "book_id": token_doc["book_id"]}

async def record_sale(invoice_id, user_id, amount, currency):
    await purchases_collection.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": {
            "status": "paid",
            "final_amount": amount,
            "currency": currency,
            "paid_at": get_now_utc()
        }}
    )

async def calc_statistics():
    total_users = await users_collection.count_documents({})
    total_categories = await categories_collection.count_documents({})
    total_books = await books_collection.count_documents({})
    total_sales_count = await purchases_collection.count_documents({"status": "paid"})
    
    pipeline = [
        {"$match": {"status": "paid"}},
        {"$group": {"_id": None, "total_revenue": {"$sum": "$amount"}}}
    ]
    
    cursor = await purchases_collection.aggregate(pipeline)
    sales_agg = await cursor.to_list(length=1)
    
    return {
        'total_users': total_users,
        'total_categories': total_categories,
        'total_books': total_books,
        'total_sales_count': total_sales_count,
        'sales_agg': sales_agg
    }

async def update_category_name(old_name: str, new_name: str):
    await categories_collection.update_one({"name": old_name}, {"$set": {"name": new_name}})
    
    await books_collection.update_many({"category": old_name}, {"$set": {"category": new_name}})
    return True

async def search_books_by_title_for_admin(title_query: str):
    cursor = books_collection.find({"title": {"$regex": title_query, "$options": "i"}})
    return await cursor.to_list(length=10)

async def update_book_field(book_id: str, field_name: str, new_value):
    await books_collection.update_one(
        {"_id": ObjectId(book_id)}, 
        {"$set": {field_name: new_value}}
    )
    return True

async def delete_book_from_db(book_id):
    await books_collection.delete_one({"_id": ObjectId(book_id)})

async def delete_category_from_db(category_name):
    await categories_collection.delete_one({"name": category_name})

import math

async def get_unique_buyers(page: int, limit: int = 5):
    """
    دریافت لیست خریداران یکتا با استفاده از $lookup برای اتصال به کالکشن users
    """
    skip = (page - 1) * limit
    
    pipeline = [
        # مرحله ۱: فقط خریدهای موفق (وضعیت paid)
        {"$match": {"status": "paid"}},
        
        # مرحله ۲: گروه‌بندی بر اساس user_id
        {"$group": {
            "_id": "$user_id",
            "purchase_count": {"$sum": 1},
            "total_spent": {"$sum": "$amount"}, # جمع مبالغ (تومان)
            "last_purchase_date": {"$max": "$paid_at"} # آخرین تاریخ پرداخت
        }},
        
        # مرحله ۳: جوین با کالکشن users
        {"$lookup": {
            "from": "users",           # نام کالکشن کاربران
            "localField": "_id",       # فیلد user_id گروه بندی شده در purchases
            "foreignField": "user_id", # فیلد user_id در users
            "as": "user_details"
        }},
        
        # مرحله ۴: باز کردن آرایه جوین شده
        {"$unwind": {"path": "$user_details", "preserveNullAndEmptyArrays": True}},
        
        # مرحله ۵: مرتب‌سازی از جدیدترین به قدیمی‌ترین خریدار
        {"$sort": {"last_purchase_date": -1}},
    ]
    
    # گرفتن تعداد کل برای محاسبه صفحات
    # (نیاز به وارد کردن purchases_collection از فایل دیتابیس دارید)
    cursor = await purchases_collection.aggregate(pipeline)
    full_result = await cursor.to_list(length=None)
    total_count = len(full_result)
    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
    
    # اجرای کوئری با صفحه‌بندی
    paginated_pipeline = pipeline + [
        {"$skip": skip},
        {"$limit": limit}
    ]
    cursor = await purchases_collection.aggregate(paginated_pipeline)
    buyers = await cursor.to_list(length=limit)
    
    return buyers, total_pages, total_count

async def check_is_admin(user_id: int, super_admin_id: int):
    if user_id == super_admin_id:
        return True
    user = await users_collection.find_one({"user_id": user_id, "role": "admin"})
    return bool(user)

async def make_user_admin(target_user_id: int):
    user = await users_collection.find_one({"user_id": target_user_id})
    if not user:
        return False
    await users_collection.update_one({"user_id": target_user_id}, {"$set": {"role": "admin"}})
    return True

async def remove_user_admin(target_user_id: int):
    await users_collection.update_one({"user_id": target_user_id}, {"$set": {"role": "user"}})

async def get_all_admins():
    cursor = users_collection.find({"role": "admin"})
    return await cursor.to_list(length=None)

async def upgrade_database():
    # ۱. اضافه کردن نقش 'user' به تمام کاربرانی که فیلد role را ندارند
    result = await users_collection.update_many(
        {"role": {"$exists": False}}, 
        {"$set": {"role": "user"}}
    )
    print(f"Updated {result.modified_count} users with default 'user' role.")
    
    # ۲. ارتقای ادمین اصلی به super_admin
    # آیدی عددی خودتان (ادمین اصلی) را وارد کنید
    super_admin_id = 123456789 
    await users_collection.update_one(
        {"user_id": super_admin_id}, 
        {"$set": {"role": "super_admin"}}
    )
    print("Super admin role configured successfully.")

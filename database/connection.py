from pymongo import AsyncMongoClient
from config import MONGO_URI, DB_NAME

client = AsyncMongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db['users']
categories_collection = db['categories']
books_collection = db['books']
purchases_collection = db['purchases']
links_collection = db['download_links'] 
settings_collection = db['settings']
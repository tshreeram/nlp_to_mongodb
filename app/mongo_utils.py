from pymongo import MongoClient
from config import Config

client = MongoClient(Config.MONGODB_URI)
db = client[Config.DATABASE_NAME]

def get_collections():
    """Fetch the list of collections in the database."""
    return db.list_collection_names()

def get_collection_keys(collection_name):
    """Fetch keys of the first document in a collection."""
    sample_doc = db[collection_name].find_one()
    return list(sample_doc.keys()) if sample_doc else []

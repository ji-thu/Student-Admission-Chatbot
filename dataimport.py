import json
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["chatbot_db"]
collection = db["intents"]

with open("intents.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for intent in data["intents"]:
    intent["intent"] = intent["intent"].lower()
    collection.replace_one({"intent": intent["intent"]}, intent, upsert=True)

print("Imported to MongoDB")

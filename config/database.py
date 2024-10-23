from pymongo import MongoClient


client = MongoClient("mongodb://kelompok5:kelompok5@localhost:27017/chicago_crime")

db = client.chicago_crime

collection_name = db["chicago_crime"]

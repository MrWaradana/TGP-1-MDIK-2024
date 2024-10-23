from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.mongo_client import MongoClient
from routes.route import router
import uvicorn


app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ? Cloud MongoDB uri
cloudUri = "mongodb+srv://admin:1te02CAr7pblQtix@cluster0.jdp8i.mongodb.net/"

# ? Local Docker uri
uri = "mongodb://kelompok5:kelompok5@localhost:27017/chicago_crime"

client = MongoClient(uri)

try:
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # Number of worker processes
        limit_concurrency=1000,  # Limit concurrent connections
        limit_max_requests=50000,  # Limit max requests per worker
        timeout_keep_alive=30,  # Keep-alive timeout
        backlog=2048,  # Connection queue size
        loop="uvloop",  # Use uvloop for better performance
        proxy_headers=True,
        forwarded_allow_ips="*",
    )

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import uuid
import time

# Redis connection
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_password = os.getenv("REDIS_PASSWORD")

r = redis.Redis(
    host=redis_host,
    port=int(redis_port),
    password=redis_password,
    decode_responses=True
)

# FastAPI setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory message storage (no database!)
room_messages = {}

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/room/create")
def create_room():
    room_code = str(uuid.uuid4())[:8].upper()
    r.setex(f"room:{room_code}", 3600, "active")  # Only store room existence
    room_messages[room_code] = []  # Empty messages list
    return {"room_code": room_code}

@app.get("/room/{room_code}/exists")
def check_room(room_code: str):
    exists = r.exists(f"room:{room_code}")
    return {"exists": exists}

@app.post("/message/{room_code}")
def send_message(room_code: str, message: str, user: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}
    
    if room_code not in room_messages:
        room_messages[room_code] = []
    
    # Add new message (no database storage!)
    new_message = {
        "user": user,
        "text": message,
        "time": time.time()
    }
    room_messages[room_code].append(new_message)
    
    # Keep only last 50 messages in memory
    if len(room_messages[room_code]) > 50:
        room_messages[room_code] = room_messages[room_code][-50:]
    
    return {"status": "success"}

@app.get("/messages/{room_code}")
def get_messages(room_code: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}
    
    # Return messages from memory, not database
    messages = room_messages.get(room_code, [])
    return {"messages": messages}
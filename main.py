from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import uuid
import json
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

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/room/create")
def create_room():
    room_code = str(uuid.uuid4())[:8].upper()
    r.setex(f"room:{room_code}", 3600, "active")
    # Initialize empty messages list
    r.set(f"messages:{room_code}", json.dumps([]))
    return {"room_code": room_code}

@app.get("/room/{room_code}/exists")
def check_room(room_code: str):
    exists = r.exists(f"room:{room_code}")
    return {"exists": exists}

@app.post("/message/{room_code}")
def send_message(room_code: str, message: str, user: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}
    
    # Get current messages
    messages_json = r.get(f"messages:{room_code}") or "[]"
    messages = json.loads(messages_json)
    
    # Add new message
    new_message = {
        "user": user,
        "text": message,
        "time": time.time()
    }
    messages.append(new_message)
    
    # Keep only last 50 messages
    if len(messages) > 50:
        messages = messages[-50:]
    
    # Save back to Redis
    r.setex(f"messages:{room_code}", 3600, json.dumps(messages))
    return {"status": "success"}

@app.get("/messages/{room_code}")
def get_messages(room_code: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}
    
    messages_json = r.get(f"messages:{room_code}") or "[]"
    messages = json.loads(messages_json)
    return {"messages": messages}
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

# In-memory message storage
room_messages = {}

def add_system_message(room_code: str, text: str):
    """Add system message to room."""
    msg = {"user": "System", "text": text, "time": time.time()}
    room_messages.setdefault(room_code, []).append(msg)
    # Keep only last 50
    if len(room_messages[room_code]) > 50:
        room_messages[room_code] = room_messages[room_code][-50:]


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.post("/room/create")
def create_room():
    room_code = str(uuid.uuid4())[:8].upper()
    r.setex(f"room:{room_code}", 3600, "active")
    r.set(f"room:{room_code}:count", 0)  # track user count
    room_messages[room_code] = []
    return {"room_code": room_code}


@app.get("/room/{room_code}/exists")
def check_room(room_code: str):
    exists = r.exists(f"room:{room_code}")
    return {"exists": exists}


@app.post("/join/{room_code}")
def join_room(room_code: str, user: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}

    # Increment user count
    r.incr(f"room:{room_code}:count")

    # Add system join message
    add_system_message(room_code, f"<b>{user}</b> joined the chat")

    return {"status": "joined"}


@app.post("/leave/{room_code}")
def leave_room(room_code: str, user: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}

    # Decrement user count
    count = r.decr(f"room:{room_code}:count")

    # Add system leave message
    add_system_message(room_code, f"<b>{user}</b> left the chat")

    # If no users left, clean up
    if count <= 0:
        r.delete(f"room:{room_code}")
        r.delete(f"room:{room_code}:count")
        room_messages.pop(room_code, None)

    return {"status": "left"}


@app.post("/message/{room_code}")
def send_message(room_code: str, message: str, user: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}

    new_message = {"user": user, "text": message, "time": time.time()}
    room_messages.setdefault(room_code, []).append(new_message)

    if len(room_messages[room_code]) > 50:
        room_messages[room_code] = room_messages[room_code][-50:]

    return {"status": "success"}


@app.get("/messages/{room_code}")
def get_messages(room_code: str):
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}
    return {"messages": room_messages.get(room_code, [])}


# --- Typing indicator ---
@app.post("/typing/{room_code}")
def typing(room_code: str, user: str):
    """Mark user as typing for 3s"""
    if not r.exists(f"room:{room_code}"):
        return {"error": "Room not found"}

    r.setex(f"room:{room_code}:typing:{user}", 3, "yes")
    return {"status": "typing"}


@app.get("/typing/{room_code}")
def get_typing(room_code: str):
    """Return list of users typing in this room"""
    keys = r.keys(f"room:{room_code}:typing:*")
    users = [k.split(":")[-1] for k in keys]
    return {"typing": users}

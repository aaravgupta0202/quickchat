from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import uuid
import time
import threading
from typing import Dict, Set, List

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

# In-memory storage
room_messages: Dict[str, List[Dict]] = {}
typing_users: Dict[str, Set[str]] = {}
active_users: Dict[str, Set[str]] = {}
room_creation_times: Dict[str, float] = {}

def add_system_message(room_code: str, text: str):
    """Add system message to room."""
    msg = {"user": "System", "text": text, "time": time.time()}
    room_messages.setdefault(room_code, []).append(msg)
    # Keep only last 50 messages
    if len(room_messages[room_code]) > 50:
        room_messages[room_code] = room_messages[room_code][-50:]

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/room/create")
def create_room():
    room_code = str(uuid.uuid4())[:8].upper()
    r.setex(f"room:{room_code}", 3600, "active")  # 1 hour expiration
    room_creation_times[room_code] = time.time()
    room_messages[room_code] = []
    active_users[room_code] = set()
    return {"room_code": room_code}

@app.get("/room/{room_code}/exists")
def check_room(room_code: str):
    exists = r.exists(f"room:{room_code}")
    if exists:
        return {"exists": True, "time_remaining": get_time_remaining(room_code)}
    return {"exists": False}

def get_time_remaining(room_code: str):
    """Get time remaining in minutes"""
    ttl = r.ttl(f"room:{room_code}")
    if ttl > 0:
        return max(0, ttl // 60)  # Return minutes remaining
    return 0

@app.post("/join/{room_code}")
def join_room(room_code: str, user: str):
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Add user to active users
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    # Add system join message
    add_system_message(room_code, f"<b>{user}</b> joined the chat")
    
    return {"status": "joined", "time_remaining": get_time_remaining(room_code)}

@app.post("/leave/{room_code}")
def leave_room(room_code: str, user: str):
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Remove user from active users
    if room_code in active_users and user in active_users[room_code]:
        active_users[room_code].remove(user)
    
    # Remove from typing users
    if room_code in typing_users and user in typing_users[room_code]:
        typing_users[room_code].remove(user)
    
    # Add system leave message
    add_system_message(room_code, f"<b>{user}</b> left the chat")
    
    return {"status": "left"}

@app.post("/message/{room_code}")
def send_message(room_code: str, message: str, user: str):
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Keep user active
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    new_message = {"user": user, "text": message, "time": time.time()}
    room_messages.setdefault(room_code, []).append(new_message)
    
    if len(room_messages[room_code]) > 50:
        room_messages[room_code] = room_messages[room_code][-50:]
    
    return {"status": "success"}

@app.get("/messages/{room_code}")
def get_messages(room_code: str):
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    return {"messages": room_messages.get(room_code, [])}

@app.post("/typing/{room_code}")
def typing_indicator(room_code: str, user: str):
    """Track typing indicator"""
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Keep user active
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    # Initialize room typing users if not exists
    if room_code not in typing_users:
        typing_users[room_code] = set()
    
    # Add user to typing set
    typing_users[room_code].add(user)
    
    # Schedule removal after 3 seconds
    def remove_typing_user():
        time.sleep(3)
        if room_code in typing_users and user in typing_users[room_code]:
            typing_users[room_code].remove(user)
            # Clean up empty sets
            if not typing_users[room_code]:
                del typing_users[room_code]
    
    # Run in background
    threading.Thread(target=remove_typing_user, daemon=True).start()
    
    return {"status": "typing"}

@app.get("/typing/{room_code}")
def get_typing_users(room_code: str):
    """Get users currently typing"""
    if room_code not in typing_users:
        return {"typing": []}
    
    # Return list of typing users
    return {"typing": list(typing_users[room_code])}

@app.get("/room/{room_code}/info")
def get_room_info(room_code: str):
    """Get room information including time remaining and user count"""
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Count only user messages (not system messages)
    user_messages = [
        msg for msg in room_messages.get(room_code, []) 
        if msg.get("user") != "System"
    ]
    
    return {
        "exists": True,
        "time_remaining": get_time_remaining(room_code),
        "user_count": len(active_users.get(room_code, set())),
        "message_count": len(user_messages),
        "active_users": list(active_users.get(room_code, set()))
    }

# New endpoint for chat name management
@app.get("/room/{room_code}/name")
def get_room_name(room_code: str):
    """Get the chat room name"""
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    chat_name = r.get(f"room:{room_code}:name") or "New Chat"
    return {"chat_name": chat_name}

@app.post("/room/{room_code}/name")
def set_room_name(room_code: str, user: str, chat_name: str):
    """Set the chat room name and notify everyone"""
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Store in Redis database
    r.setex(f"room:{room_code}:name", 3600, chat_name)
    
    # Add system message about name change
    add_system_message(room_code, f"<b>{user}</b> changed the chat name to \"<b>{chat_name}</b>\"")
    
    return {"status": "success", "chat_name": chat_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import uuid
import json
import time
from typing import Dict, List
from pydantic import BaseModel

# ---------------------------
# Redis connection
# ---------------------------
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_password = os.getenv("REDIS_PASSWORD")

if not all([redis_host, redis_port, redis_password]):
    raise ConnectionError("Redis environment variables not set")

r = redis.Redis(
    host=redis_host,
    port=int(redis_port),
    password=redis_password,
    decode_responses=True
)

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI(title="Chat Room Backend")

# CORS configuration
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# In-memory storage for messages
# ---------------------------
# This stores messages temporarily (resets on server restart)
# For production, you might want to use Redis for this too
chat_messages: Dict[str, List[Dict]] = {}

# ---------------------------
# Models
# ---------------------------
class MessageModel(BaseModel):
    room_code: str
    user_name: str
    content: str

class JoinRoomModel(BaseModel):
    room_code: str
    user_name: str

class CreateRoomModel(BaseModel):
    user_name: str

# ---------------------------
# Endpoints
# ---------------------------

@app.get("/")
def root():
    return {"message": "Chat Room Backend Running 🚀"}

@app.get("/room/{room_code}/exists")
def check_room_exists(room_code: str):
    """Check if a room exists"""
    exists = r.exists(f"room:{room_code}")
    return {"exists": exists}

@app.post("/room/create")
def create_room(room_data: CreateRoomModel):
    """Create a new chat room"""
    room_code = str(uuid.uuid4())[:8].upper()  # Generate a simple 8-character code
    r.setex(f"room:{room_code}", 3600, "active")  # Room expires after 1 hour
    
    # Initialize empty messages list for the room
    chat_messages[room_code] = []
    
    # Add system message for room creation
    system_message = {
        "type": "system",
        "content": f"Room created by {room_data.user_name}",
        "timestamp": time.time()
    }
    chat_messages[room_code].append(system_message)
    
    return {"room_code": room_code}

@app.post("/message")
def send_message(message: MessageModel):
    """Send a message to a room"""
    # Check if room exists
    if not r.exists(f"room:{message.room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Create message with timestamp
    timestamp = time.time()
    message_data = {
        "type": "message",
        "sender": message.user_name,
        "content": message.content,
        "timestamp": timestamp
    }
    
    # Store message in Redis (expire after 1 hour)
    message_key = f"message:{message.room_code}:{timestamp}"
    r.setex(message_key, 3600, json.dumps(message_data))
    
    # Also add to in-memory storage for quick polling
    if message.room_code not in chat_messages:
        chat_messages[message.room_code] = []
    
    chat_messages[message.room_code].append(message_data)
    
    # Keep only last 100 messages per room to prevent memory issues
    if len(chat_messages[message.room_code]) > 100:
        chat_messages[message.room_code] = chat_messages[message.room_code][-100:]
    
    return {"status": "success", "timestamp": timestamp}

@app.post("/join")
def join_room(join_data: JoinRoomModel):
    """Join a room and get recent messages"""
    # Check if room exists
    if not r.exists(f"room:{join_data.room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Initialize messages list if this is the first user
    if join_data.room_code not in chat_messages:
        chat_messages[join_data.room_code] = []
    
    # Add system message for user joining
    system_message = {
        "type": "system",
        "content": f"{join_data.user_name} joined the chat",
        "timestamp": time.time()
    }
    chat_messages[join_data.room_code].append(system_message)
    
    # Get recent messages (last 20)
    recent_messages = chat_messages[join_data.room_code][-20:] if chat_messages[join_data.room_code] else []
    
    return {
        "status": "joined",
        "recent_messages": recent_messages
    }

@app.get("/messages/{room_code}")
def get_messages(room_code: str, last_timestamp: float = 0):
    """Get new messages since last timestamp"""
    # Check if room exists
    if not r.exists(f"room:{room_code}"):
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_code not in chat_messages:
        return {"messages": []}
    
    # Filter messages newer than last_timestamp
    new_messages = [
        msg for msg in chat_messages[room_code] 
        if msg["timestamp"] > last_timestamp
    ]
    
    return {"messages": new_messages}

@app.post("/leave")
def leave_room(leave_data: JoinRoomModel):
    """User leaves a room"""
    if leave_data.room_code in chat_messages:
        system_message = {
            "type": "system",
            "content": f"{leave_data.user_name} left the chat",
            "timestamp": time.time()
        }
        chat_messages[leave_data.room_code].append(system_message)
    
    return {"status": "left"}

@app.delete("/room/{room_code}")
def delete_room(room_code: str):
    """Delete a room (admin function)"""
    if r.exists(f"room:{room_code}"):
        r.delete(f"room:{room_code}")
        if room_code in chat_messages:
            del chat_messages[room_code]
        return {"status": "deleted"}
    else:
        raise HTTPException(status_code=404, detail="Room not found")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        r.ping()
        return {
            "status": "healthy",
            "redis": "connected",
            "rooms_count": len(chat_messages),
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis connection failed: {str(e)}")

# Background task to clean up expired rooms
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("Chat Room Backend started successfully!")
    print(f"Frontend URL: {frontend_url}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("Shutting down Chat Room Backend")
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import uuid
import json
from typing import Dict, List

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
# CORS configuration - UPDATE THIS
frontend_url = os.getenv("FRONTEND_URL", "https://rever-app.netlify.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_names: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, room_code: str, user_name: str):
        await websocket.accept()
        
        if room_code not in self.active_connections:
            self.active_connections[room_code] = []
            # Store room in Redis with 1-hour expiration
            r.setex(f"room:{room_code}", 3600, "active")
        
        self.active_connections[room_code].append(websocket)
        # Store user info
        self.user_names[id(websocket)] = user_name
        
        # Notify room that user joined
        await self.broadcast_system_message(room_code, f"{user_name} joined the chat")
        
        return room_code

    def disconnect(self, websocket: WebSocket, room_code: str):
        if room_code in self.active_connections and websocket in self.active_connections[room_code]:
            self.active_connections[room_code].remove(websocket)
            user_name = self.user_names.get(id(websocket), "Someone")
            
            # Remove room if empty
            if len(self.active_connections[room_code]) == 0:
                del self.active_connections[room_code]
                # Remove from Redis
                r.delete(f"room:{room_code}")
            
            # Remove user info
            if id(websocket) in self.user_names:
                del self.user_names[id(websocket)]
            
            return user_name

    async def broadcast(self, room_code: str, message: str, sender_name: str):
        if room_code in self.active_connections:
            message_data = {
                "type": "message",
                "sender": sender_name,
                "content": message,
                "timestamp": os.times().user  # Simple timestamp
            }
            for connection in self.active_connections[room_code]:
                try:
                    await connection.send_json(message_data)
                except:
                    pass

    async def broadcast_system_message(self, room_code: str, message: str):
        if room_code in self.active_connections:
            message_data = {
                "type": "system",
                "content": message,
                "timestamp": os.times().user
            }
            for connection in self.active_connections[room_code]:
                try:
                    await connection.send_json(message_data)
                except:
                    pass

manager = ConnectionManager()

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
def create_room():
    """Create a new chat room"""
    room_code = str(uuid.uuid4())[:8].upper()  # Generate a simple 8-character code
    r.setex(f"room:{room_code}", 3600, "active")  # Room expires after 1 hour
    return {"room_code": room_code}

# WebSocket endpoint for chat
@app.websocket("/ws/{room_code}/{user_name}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_name: str):
    # Connect to the room
    await manager.connect(websocket, room_code, user_name)
    
    try:
        while True:
            # Wait for messages from the client
            data = await websocket.receive_text()
            # Broadcast the message to everyone in the room
            await manager.broadcast(room_code, data, user_name)
    except WebSocketDisconnect:
        # Handle disconnection
        user_name = manager.disconnect(websocket, room_code)
        await manager.broadcast_system_message(room_code, f"{user_name} left the chat")
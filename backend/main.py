from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import time
import threading
from typing import Dict, Set, List
from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from cryptography.fernet import Fernet, InvalidToken
import base64

# Database setup
# SQLite fallback is used for local development when DATABASE_URL is not set.
# In production (Render with Neon DB), provide the DATABASE_URL environment variable.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Setup SQLAlchemy engine. We handle SQLite specially to allow multi-threading in dev mode.
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
# SessionLocal is the factory for creating new database sessions per request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base class for all SQLAlchemy declarative models
Base = declarative_base()

class Room(Base):
    __tablename__ = "rooms"
    room_code = Column(String, primary_key=True, index=True)
    created_at = Column(Float, default=time.time)
    chat_name = Column(String, default="New Chat")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_code = Column(String, index=True)
    user_name = Column(String)
    text = Column(String)
    time = Column(Float, default=time.time)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI setup
app = FastAPI()

# Encryption Setup
# Use a static fallback key for local dev if not provided, but it's highly recommended to set one.
# MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI= is base64 for '12345678901234567890123456789012' (32 bytes)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI=")
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_message(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()

def decrypt_message(encrypted_text: str) -> str:
    try:
        return fernet.decrypt(encrypted_text.encode()).decode()
    except (InvalidToken, Exception):
        # Fallback for old unencrypted messages or if key changes
        return encrypted_text

# CORS Security setup
# Get the allowed origin from the .env file. 
# In production, this should be your exact Netlify domain (e.g., https://my-quickchat.netlify.app)
# If not set, it defaults to "*" for easier local development.
frontend_url = os.getenv("FRONTEND_URL", "*")
allowed_origins = [frontend_url] if frontend_url != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], # Restricted from ["*"] to specific methods
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Endpoint for uptime monitors to prevent Render inactivity spin down."""
    return {"status": "ok", "timestamp": time.time()}

# In-memory storage for transient state (saves expensive DB writes for serverless environments)
# typing_users: Tracks which users are currently typing in which room
typing_users: Dict[str, Set[str]] = {}
# active_users: Tracks users who have recently joined or interacted in a room
active_users: Dict[str, Set[str]] = {}

def add_system_message(db: Session, room_code: str, text: str):
    """Add system message to room."""
    encrypted_text = encrypt_message(text)
    msg = Message(room_code=room_code, user_name="System", text=encrypted_text, time=time.time())
    db.add(msg)
    db.commit()
    cleanup_old_messages(db, room_code)

def cleanup_old_messages(db: Session, room_code: str):
    """Keep only last 50 messages."""
    count = db.query(Message).filter(Message.room_code == room_code).count()
    if count > 50:
        # Delete oldest
        to_delete = count - 50
        oldest = db.query(Message).filter(Message.room_code == room_code).order_by(Message.time.asc()).limit(to_delete).all()
        for m in oldest:
            db.delete(m)
        db.commit()

def cleanup_expired_rooms(db: Session):
    """Delete rooms older than 1 hour"""
    cutoff = time.time() - 3600
    expired = db.query(Room).filter(Room.created_at < cutoff).all()
    for room in expired:
        db.query(Message).filter(Message.room_code == room.room_code).delete()
        db.delete(room)
        # cleanup memory
        if room.room_code in typing_users:
            del typing_users[room.room_code]
        if room.room_code in active_users:
            del active_users[room.room_code]
    if expired:
        db.commit()

@app.middleware("http")
async def db_session_middleware(request, call_next):
    # Run cleanup occasionally on requests
    if time.time() % 10 < 1:  # ~10% chance per request
        db = SessionLocal()
        cleanup_expired_rooms(db)
        db.close()
    response = await call_next(request)
    return response

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/room/create")
def create_room(db: Session = Depends(get_db)):
    room_code = str(uuid.uuid4())[:8].upper()
    
    new_room = Room(room_code=room_code, created_at=time.time(), chat_name="New Chat")
    db.add(new_room)
    db.commit()
    
    active_users[room_code] = set()
    return {"room_code": room_code}

@app.get("/room/{room_code}/exists")
def check_room(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if room:
        return {"exists": True, "time_remaining": max(0, int(3600 - (time.time() - room.created_at)) // 60)}
    return {"exists": False}

@app.post("/join/{room_code}")
def join_room(room_code: str, user: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    add_system_message(db, room_code, f"<b>{user}</b> joined the chat")
    
    time_rem = max(0, int(3600 - (time.time() - room.created_at)) // 60)
    return {"status": "joined", "time_remaining": time_rem}

@app.post("/leave/{room_code}")
def leave_room(room_code: str, user: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_code in active_users and user in active_users[room_code]:
        active_users[room_code].remove(user)
    
    if room_code in typing_users and user in typing_users[room_code]:
        typing_users[room_code].remove(user)
    
    add_system_message(db, room_code, f"<b>{user}</b> left the chat")
    return {"status": "left"}

@app.post("/message/{room_code}")
def send_message(room_code: str, message: str, user: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    new_message = Message(room_code=room_code, user_name=user, text=message, time=time.time())
    db.add(new_message)
    db.commit()
    cleanup_old_messages(db, room_code)
    
    return {"status": "success"}

@app.get("/messages/{room_code}")
def get_messages(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    messages = db.query(Message).filter(Message.room_code == room_code).order_by(Message.time.asc()).all()
    
    decrypted_messages = []
    for m in messages:
        decrypted_messages.append({
            "user": m.user_name,
            "text": decrypt_message(m.text),
            "time": m.time
        })
        
    return {"messages": decrypted_messages}

@app.post("/message/{room_code}")
def post_message(room_code: str, message: str, user: str, db: Session = Depends(get_db)):
    room_code = room_code.upper()
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    encrypted_text = encrypt_message(message)
    msg = Message(room_code=room_code, user_name=user, text=encrypted_text, time=time.time())
    db.add(msg)
    db.commit()
    cleanup_old_messages(db, room_code)
    
    # Mark user as active
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    return {"status": "success"}

@app.post("/typing/{room_code}")
def typing_indicator(room_code: str, user: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if room_code not in active_users:
        active_users[room_code] = set()
    active_users[room_code].add(user)
    
    if room_code not in typing_users:
        typing_users[room_code] = set()
    typing_users[room_code].add(user)
    
    # Schedule automatic removal of the typing indicator after 3 seconds
    def remove_typing_user():
        time.sleep(3)
        if room_code in typing_users and user in typing_users[room_code]:
            typing_users[room_code].remove(user)
            # Clean up empty dictionary keys to prevent memory leaks
            if not typing_users[room_code]:
                del typing_users[room_code]
    
    # Run the removal in a background daemon thread
    threading.Thread(target=remove_typing_user, daemon=True).start()
    return {"status": "typing"}

@app.get("/typing/{room_code}")
def get_typing_users(room_code: str):
    if room_code not in typing_users:
        return {"typing": []}
    return {"typing": list(typing_users[room_code])}

@app.get("/room/{room_code}/info")
def get_room_info(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    user_messages_count = db.query(Message).filter(Message.room_code == room_code, Message.user_name != "System").count()
    time_rem = max(0, int(3600 - (time.time() - room.created_at)) // 60)
    
    return {
        "exists": True,
        "time_remaining": time_rem,
        "user_count": len(active_users.get(room_code, set())),
        "message_count": user_messages_count,
        "active_users": list(active_users.get(room_code, set()))
    }

@app.get("/room/{room_code}/name")
def get_room_name(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"chat_name": room.chat_name}

@app.post("/room/{room_code}/name")
def set_room_name(room_code: str, user: str, chat_name: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.room_code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room.chat_name = chat_name
    db.commit()
    
    add_system_message(db, room_code, f"<b>{user}</b> changed the chat name to \"<b>{chat_name}</b>\"")
    return {"status": "success", "chat_name": chat_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import os
import redis
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------
# Redis connection
# ---------------------------
# Render provides a single REDIS_URL environment variable.
# We need to parse this URL to get the host, port, and password.
redis_url = os.getenv("REDIS_URL")

if redis_url:
    url = urlparse(redis_url)
    r = redis.Redis(
        host=url.hostname,
        port=url.port,
        password=url.password,
        decode_responses=True
    )
    print("Connected to Redis using Render's REDIS_URL.")
else:
    # Fallback to localhost for local development
    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        decode_responses=True
    )
    print("Connected to local Redis.")

# Check the connection
try:
    r.ping()
    print("Redis connection successful!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    # You might want to raise an exception here to prevent the app from starting
    # raise HTTPException(status_code=500, detail="Database connection failed")

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI(title="REVER Backend")

# Define allowed origins for CORS.
# You can get your Netlify URL from your Netlify dashboard.
# It should look something like "https://your-site-name.netlify.app".
# Replace the placeholder URL below with your actual Netlify URL.
# It is best practice to get this from an environment variable on Render.
# For example, you can set an env var called 'FE_URL' in Render's dashboard.
# Then, fetch the value using: os.getenv("FE_URL")
FE_URL = "https://rever-app.netlify.app/" # <--- REPLACE THIS

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000", # Common for React/Vue dev servers
    FE_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Models
# ---------------------------
class RegisterModel(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class UpdateModel(BaseModel):
    email: EmailStr
    name: str | None = None
    password: str | None = None

class DeleteModel(BaseModel):
    email: EmailStr

# ---------------------------
# Endpoints
# ---------------------------

@app.get("/")
def root():
    return {"message": "Backend running successfully 🚀"}

@app.post("/register")
def register(user: RegisterModel):
    if r.exists(user.email):
        raise HTTPException(status_code=400, detail="User already exists")

    r.hset(user.email, mapping={"name": user.name, "password": user.password})
    return {"message": "User registered successfully"}

@app.post("/login")
def login(user: LoginModel):
    if not r.exists(user.email):
        raise HTTPException(status_code=404, detail="User not found")

    stored_password = r.hget(user.email, "password")
    if stored_password != user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful"}

@app.post("/update")
def update(user: UpdateModel):
    if not r.exists(user.email):
        raise HTTPException(status_code=404, detail="User not found")

    if user.name:
        r.hset(user.email, "name", user.name)
    if user.password:
        r.hset(user.email, "password", user.password)

    return {"message": "Account updated successfully"}

@app.delete("/delete")
def delete(user: DeleteModel):
    if not r.exists(user.email):
        raise HTTPException(status_code=404, detail="User not found")

    r.delete(user.email)
    return {"message": "Account deleted successfully"}

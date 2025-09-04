from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import redis
import os
from fastapi.middleware.cors import CORSMiddleware


# ---------------------------
# Redis connection
# ---------------------------
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", 6379)
redis_password = os.getenv("REDIS_PASSWORD", None)

r = redis.Redis(
    host=redis_host,
    port=int(redis_port),
    password=redis_password,
    decode_responses=True
)

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI(title="REVER Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for testing; later restrict to your Netlify/Render frontend URL
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

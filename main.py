import os
import redis
from fastapi import FastAPI, HTTPException
from passlib.hash import bcrypt
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Redis connection (use env variables in Render/.env)
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    username=os.getenv("REDIS_USER", None),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True
)

app = FastAPI(title="REVER Backend")

# ------------------ Models ------------------

class RegisterUser(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginUser(BaseModel):
    email: EmailStr
    password: str

class UpdateUser(BaseModel):
    email: EmailStr
    name: str | None = None
    password: str | None = None


def user_key(email: str):
    return f"user:{email}"

# ------------------ Routes ------------------

@app.get("/")
def root():
    return {"status": "Backend running ✅"}


@app.post("/register")
def register(user: RegisterUser):
    if r.exists(user_key(user.email)):
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = bcrypt.hash(user.password)
    now = datetime.utcnow().isoformat()

    r.hset(
        user_key(user.email),
        mapping={
            "name": user.name,
            "email": user.email,
            "password": hashed_pw,
            "created_at": now,
            "updated_at": now,
        },
    )
    return {"message": "User registered successfully"}


@app.post("/login")
def login(user: LoginUser):
    db_user = r.hgetall(user_key(user.email))
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.verify(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful", "name": db_user.get("name")}


@app.post("/update")
def update(user: UpdateUser):
    if not r.exists(user_key(user.email)):
        raise HTTPException(status_code=404, detail="Account not found")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if user.name:
        updates["name"] = user.name
    if user.password:
        updates["password"] = bcrypt.hash(user.password)

    r.hset(user_key(user.email), mapping=updates)
    return {"message": "Account updated successfully"}


@app.delete("/delete/{email}")
def delete(email: EmailStr):
    if not r.exists(user_key(email)):
        raise HTTPException(status_code=404, detail="Account not found")

    r.delete(user_key(email))
    return {"message": "Account deleted successfully"}

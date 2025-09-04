from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import redis
import os
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import ConnectionError

# ---------------------------
# Redis connection
# ---------------------------
# Use individual environment variables as provided by the user
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_password = os.getenv("REDIS_PASSWORD")

# Check that all necessary environment variables are set
if not all([redis_host, redis_port, redis_password]):
    raise ConnectionError("One or more Redis environment variables are not set. Ensure REDIS_HOST, REDIS_PORT, and REDIS_PASSWORD are configured.")

# Use the individual variables to connect
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

# Get the frontend URL from an environment variable for security and flexibility
# Use a default value for local development
FE_URL = os.getenv("FE_URL", "http://localhost:3000")

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
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
    print(f"Received a request to register user: {user.email}") # Debugging print statement
    try:
        # PING the Redis server to check the connection before proceeding
        r.ping()
        if r.exists(user.email):
            raise HTTPException(status_code=400, detail="User already exists")

        r.hset(user.email, mapping={"name": user.name, "password": user.password})
        return {"message": "User registered successfully"}
    except ConnectionError as e:
        print(f"Redis Connection Error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to Redis database.")

@app.post("/login")
def login(user: LoginModel):
    try:
        r.ping()
        if not r.exists(user.email):
            raise HTTPException(status_code=404, detail="User not found")

        stored_password = r.hget(user.email, "password")
        if stored_password != user.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return {"message": "Login successful"}
    except ConnectionError as e:
        print(f"Redis Connection Error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to Redis database.")

@app.post("/update")
def update(user: UpdateModel):
    try:
        r.ping()
        if not r.exists(user.email):
            raise HTTPException(status_code=404, detail="User not found")

        if user.name:
            r.hset(user.email, "name", user.name)
        if user.password:
            r.hset(user.email, "password", user.password)

        return {"message": "Account updated successfully"}
    except ConnectionError as e:
        print(f"Redis Connection Error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to Redis database.")

@app.delete("/delete")
def delete(user: DeleteModel):
    try:
        r.ping()
        if not r.exists(user.email):
            raise HTTPException(status_code=404, detail="User not found")

        r.delete(user.email)
        return {"message": "Account deleted successfully"}
    except ConnectionError as e:
        print(f"Redis Connection Error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to Redis database.")

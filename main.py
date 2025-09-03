import os
import redis

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    username="default",
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)
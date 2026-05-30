from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import redis
import os
from app.core.config import settings

# SQLAlchemy Setup
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Redis Setup (Mocked if running tests)
if os.getenv("TESTING") == "True":
    class MockRedis:
        def __init__(self):
            self.store = {}
            self.pubsub_channels = {}

        def get(self, key):
            return self.store.get(key)

        def set(self, key, value, ex=None):
            self.store[key] = str(value)
            return True

        def setex(self, key, time, value):
            self.store[key] = str(value)
            return True

        def incr(self, key):
            val = int(self.store.get(key, 0)) + 1
            self.store[key] = str(val)
            return val

        def decr(self, key):
            val = int(self.store.get(key, 0)) - 1
            self.store[key] = str(val)
            return val

        def hincrby(self, name, key, amount):
            hkey = f"{name}:{key}"
            val = int(self.store.get(hkey, 0)) + amount
            self.store[hkey] = str(val)
            return val

        def ping(self):
            return True

        def publish(self, channel, message):
            if channel not in self.pubsub_channels:
                self.pubsub_channels[channel] = []
            self.pubsub_channels[channel].append(message)
            return 1

        def pubsub(self):
            class MockPubSub:
                def subscribe(self, *args, **kwargs): pass
                def get_message(self, *args, **kwargs): return None
                def unsubscribe(self, *args, **kwargs): pass
            return MockPubSub()

    redis_client = MockRedis()
else:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    return redis_client

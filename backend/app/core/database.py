from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import redis
import os
from app.core.config import settings

# SQLAlchemy Setup
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

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

# Redis Setup (Mocked in test mode or if server is unreachable)
if os.getenv("TESTING") == "True":
    redis_client = MockRedis()
else:
    try:
        import logging
        logger = logging.getLogger(__name__)
        # Ping check with timeout to prevent blocking startup
        temp_client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        temp_client.ping()
        redis_client = temp_client
        logger.info("Successfully connected to Redis server.")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not connect to Redis at {settings.REDIS_URL} ({e}). Falling back to in-memory MockRedis.")
        redis_client = MockRedis()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    return redis_client

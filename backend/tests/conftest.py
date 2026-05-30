import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os
import sys

# Set TESTING environment variable before importing main app
os.environ["TESTING"] = "True"

# Ensure backend folder is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.core.database import Base, get_db, get_redis

# Test SQLite Engine
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mock Redis Client
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
        return MockPubSub(self)

class MockPubSub:
    def __init__(self, mock_redis):
        self.mock_redis = mock_redis
        self.subscribed = []

    def subscribe(self, channel):
        self.subscribed.append(channel)

    def get_message(self, ignore_subscribe_messages=False, timeout=0):
        return None

    def unsubscribe(self, channel):
        if channel in self.subscribed:
            self.subscribed.remove(channel)

mock_redis_client = MockRedis()

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed default store and zones for testing
    db = TestingSessionLocal()
    try:
        from app.models.models import Store, Zone
        store = Store(
            id="store-mumbai-01",
            name="Purplle Flagship Store - Mumbai",
            location="Bandra, Mumbai",
            timezone="IST"
        )
        db.add(store)
        db.commit()
        
        zones = [
            Zone(store_id="store-mumbai-01", name="Entrance Zone", bounding_box=[[0,0], [100,0], [100,100], [0,100]]),
            Zone(store_id="store-mumbai-01", name="Cosmetics Section", bounding_box=[[100,0], [200,0], [200,100], [100,100]]),
            Zone(store_id="store-mumbai-01", name="Billing Queue Zone", bounding_box=[[200,0], [300,0], [300,100], [200,100]])
        ]
        for z in zones:
            db.add(z)
        db.commit()
    except Exception as e:
        print(f"Error seeding test DB: {e}")
    finally:
        db.close()
        
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_redis():
        return mock_redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()

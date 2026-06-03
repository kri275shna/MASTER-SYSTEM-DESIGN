from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.core.logging import setup_logging

# Initialize structlog configurations
setup_logging()

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.api.routes import auth, events, stores, health
from app.api.middleware.logging import StructuredLoggingMiddleware
from app.models.models import User, Store, Zone
from app.core.security import get_password_hash

# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bootstrapping FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured Logging Middleware
app.add_middleware(StructuredLoggingMiddleware)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(events.router, prefix=f"{settings.API_V1_STR}/events", tags=["events"])
app.include_router(stores.router, prefix=f"{settings.API_V1_STR}/stores", tags=["stores"])
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["health"])

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Purplle Store Intelligence API Platform is operational.",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

@app.on_event("startup")
def on_startup():
    import os
    if os.getenv("TESTING") == "True":
        logger.info("Skipping database initialization/seeding in testing environment.")
        return
    logger.info("Initializing database and seeding default values...")
    # Auto-create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Seeding defaults
    db = SessionLocal()
    try:
        # 1. Seed RBAC Users
        users_to_seed = [
            {"email": "admin@purplle.com", "password": "admin123", "full_name": "Store Admin", "role": "Admin"},
            {"email": "analyst@purplle.com", "password": "analyst123", "full_name": "Data Analyst", "role": "Analyst"},
            {"email": "viewer@purplle.com", "password": "viewer123", "full_name": "Dashboard Viewer", "role": "Viewer"}
        ]
        
        for u in users_to_seed:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if not existing:
                seeded_user = User(
                    email=u["email"],
                    hashed_password=get_password_hash(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"]
                )
                db.add(seeded_user)
                logger.info(f"Seeded User: {u['email']} with role {u['role']}")
                
        # 2. Seed default Mumbai store
        default_store_id = settings.STORE_ID_DEFAULT
        existing_store = db.query(Store).filter(Store.id == default_store_id).first()
        if not existing_store:
            store = Store(
                id=default_store_id,
                name="Purplle Flagship Store - Mumbai",
                location="Bandra, Mumbai",
                timezone="IST"
            )
            db.add(store)
            logger.info(f"Seeded default Store: {default_store_id}")
            db.commit() # Commit to ensure store exists for foreign key references
            
            # 3. Seed default Zones for this store
            zones_to_seed = [
                {"name": "Entrance Zone", "box": [[0,0], [100,0], [100,100], [0,100]]},
                {"name": "Cosmetics Section", "box": [[100,0], [200,0], [200,100], [100,100]]},
                {"name": "Billing Queue Zone", "box": [[200,0], [300,0], [300,100], [200,100]]},
                {"name": "Skin Care Section", "box": [[0,100], [100,100], [100,200], [0,200]]}
            ]
            for z in zones_to_seed:
                zone = Zone(
                    store_id=default_store_id,
                    name=z["name"],
                    bounding_box=z["box"]
                )
                db.add(zone)
                logger.info(f"Seeded Zone: {z['name']} under store {default_store_id}")
                
        db.commit()
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

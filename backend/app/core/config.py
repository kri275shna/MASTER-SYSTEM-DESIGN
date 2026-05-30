import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Purplle Store Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = Field(default="purplle-super-secret-key-change-in-production-12345", validation_alias="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    
    # Databases
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/store_intelligence", validation_alias="DATABASE_URL")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    
    # Computer Vision Settings
    YOLO_CONFIDENCE_THRESHOLD: float = 0.45
    BYTETRACK_IOU_THRESHOLD: float = 0.3
    REID_SIMILARITY_THRESHOLD: float = 0.75
    STAFF_REID_THRESHOLD: float = 0.82
    
    # System Settings
    STORE_ID_DEFAULT: str = "store-mumbai-01"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

# Instantiating settings
settings = Settings()

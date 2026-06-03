from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

class EventSchema(BaseModel):
    """
    Pydantic v2 Event Validation Schema for Store Intelligence Platform.
    
    JSON Example:
    {
      "event_id": "8b9f1d8c-2f86-4e5c-9c7b-6cde0987a0c1",
      "store_id": "store-mumbai-01",
      "camera_id": "cam-cosmetics-01",
      "visitor_id": "visitor-983",
      "event_type": "ZONE_ENTER",
      "timestamp": "2026-06-04T01:21:00Z",
      "zone_id": "zone-cosmetics",
      "dwell_ms": 120000,
      "is_staff": false,
      "confidence": 0.94,
      "metadata": {
        "x_coords": [100, 200],
        "y_coords": [150, 250]
      }
    }
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique UUID representing the event.")
    store_id: str = Field(..., description="Store Identifier where the camera is located.")
    camera_id: Optional[str] = Field(None, description="Camera ID that captured the raw CCTV feed.")
    visitor_id: str = Field(..., description="ReID resolved visitor profile ID.")
    event_type: str = Field(..., description="Type of activity: ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, QUEUE_JOIN, QUEUE_ABANDON, REENTRY.")
    timestamp: datetime = Field(..., description="DateTime string in ISO 8601 format when the event was detected.")
    zone_id: Optional[str] = Field(None, description="Identifier of the specific area or section.")
    dwell_ms: Optional[int] = Field(0, description="Dwell time in milliseconds (applicable for ZONE_EXIT, ZONE_DWELL, etc.).")
    is_staff: Optional[bool] = Field(False, description="Flag indicating if the detected person is a store employee.")
    confidence: Optional[float] = Field(1.0, description="Confidence score from YOLO detection (range: 0.0 to 1.0).")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom payload for raw parameters (coordinates, raw counts, etc.).")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "event_id": "8b9f1d8c-2f86-4e5c-9c7b-6cde0987a0c1",
                "store_id": "store-mumbai-01",
                "camera_id": "cam-cosmetics-01",
                "visitor_id": "visitor-983",
                "event_type": "ZONE_ENTER",
                "timestamp": "2026-06-04T01:21:00Z",
                "zone_id": "zone-cosmetics",
                "dwell_ms": 120000,
                "is_staff": False,
                "confidence": 0.94,
                "metadata": {
                  "x_coords": [100, 200],
                  "y_coords": [150, 250]
                }
            }
        }
    }

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        valid_types = {
            "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
            "QUEUE_JOIN", "QUEUE_ABANDON", "REENTRY"
        }
        upper_v = v.upper()
        if upper_v not in valid_types:
            raise ValueError(f"event_type must be one of {valid_types}. Got: {v}")
        return upper_v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence score must be between 0.0 and 1.0. Got: {v}")
        return v

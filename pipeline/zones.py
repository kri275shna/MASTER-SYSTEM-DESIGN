# PROMPT: Implement zone mapping and transition event detection
# CHANGES MADE: Created zones.py with pointPolygonTest mapping and state-tracking for ZONE_ENTER/EXIT events

import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger("pipeline.zones")

class ZoneManager:
    def __init__(self, zones_config: Dict[str, List[List[int]]]):
        """
        zones_config: Dict of zone_id -> list of coordinates [[x1, y1], [x2, y2], ...]
        """
        self.zones: Dict[str, np.ndarray] = {}
        for zone_id, pts in zones_config.items():
            self.zones[zone_id] = np.array(pts, dtype=np.int32)
            
        self.visitor_zone_states: Dict[str, str] = {}  # visitor_id -> current_zone_id
        self.zone_entry_timestamps: Dict[str, datetime] = {}  # visitor_id -> entry_time

    def get_zone_at_point(self, point: Tuple[int, int]) -> Optional[str]:
        """Calculates which zone contains the point using pointPolygonTest."""
        for zone_id, poly in self.zones.items():
            # Returns positive if inside, 0 if on edge, negative if outside
            dist = cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False)
            if dist >= 0:
                return zone_id
        return None

    def update_visitor_zone(self, visitor_id: str, bbox: Tuple[int, int, int, int], timestamp: datetime) -> List[Dict[str, Any]]:
        """
        Updates the zone state for a visitor.
        Calculates center-bottom (foot level) point.
        Returns generated events list (e.g. ZONE_ENTER, ZONE_EXIT).
        """
        x1, y1, x2, y2 = bbox
        foot_point = (int((x1 + x2) / 2), int(y2))
        
        current_zone = self.get_zone_at_point(foot_point)
        previous_zone = self.visitor_zone_states.get(visitor_id)
        
        events = []

        if current_zone != previous_zone:
            # 1. Visitor exited the previous zone
            if previous_zone:
                entry_time = self.zone_entry_timestamps.get(visitor_id, timestamp)
                dwell_sec = int((timestamp - entry_time).total_seconds())
                events.append({
                    "event_type": "ZONE_EXIT",
                    "visitor_id": visitor_id,
                    "zone_id": previous_zone,
                    "dwell_ms": dwell_sec * 1000,
                    "timestamp": timestamp
                })
                
            # 2. Visitor entered a new zone
            if current_zone:
                self.visitor_zone_states[visitor_id] = current_zone
                self.zone_entry_timestamps[visitor_id] = timestamp
                events.append({
                    "event_type": "ZONE_ENTER",
                    "visitor_id": visitor_id,
                    "zone_id": current_zone,
                    "dwell_ms": 0,
                    "timestamp": timestamp
                })
            else:
                # Visitor went to a dead/unconfigured area
                if visitor_id in self.visitor_zone_states:
                    del self.visitor_zone_states[visitor_id]
                if visitor_id in self.zone_entry_timestamps:
                    del self.zone_entry_timestamps[visitor_id]
                    
        return events

    def handle_visitor_exit(self, visitor_id: str, timestamp: datetime) -> List[Dict[str, Any]]:
        """
        Handles visitor exiting the camera/feed completely.
        Cleans up tracking memory and generates final ZONE_EXIT if active.
        """
        events = []
        previous_zone = self.visitor_zone_states.get(visitor_id)
        
        if previous_zone:
            entry_time = self.zone_entry_timestamps.get(visitor_id, timestamp)
            dwell_sec = int((timestamp - entry_time).total_seconds())
            events.append({
                "event_type": "ZONE_EXIT",
                "visitor_id": visitor_id,
                "zone_id": previous_zone,
                "dwell_ms": dwell_sec * 1000,
                "timestamp": timestamp
            })

        # Cleanup state
        self.visitor_zone_states.pop(visitor_id, None)
        self.zone_entry_timestamps.pop(visitor_id, None)
        
        return events

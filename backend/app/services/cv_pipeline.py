import cv2
import numpy as np
import os
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)

# YOLOv8 Person Class ID is 0
PERSON_CLASS_ID = 0

class CVInferencePipeline:
    def __init__(self):
        self.yolo_model = None
        self.staff_feature_db: List[np.ndarray] = []  # Registered staff Re-ID features
        self.initialized = False
        
        # In a real environment, we'd initialize models:
        # from ultralytics import YOLO
        # self.yolo_model = YOLO("yolov8n.pt")
        # self.initialized = True
        try:
            from ultralytics import YOLO
            # We initialize lazily or attempt loading.
            # Avoid downloading during initialization if offline.
            self.yolo_model = YOLO("yolov8n.pt")
            self.initialized = True
            logger.info("YOLOv8 model initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not load YOLOv8 model (using mock detector fallback): {e}")

    def detect_people(self, frame: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], float]]:
        """
        Runs YOLOv8 person detection on the frame.
        Returns list of (bbox, confidence) where bbox is (x1, y1, x2, y2).
        """
        detections = []
        if self.initialized and self.yolo_model is not None:
            try:
                results = self.yolo_model(frame, verbose=False)[0]
                for box in results.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    if cls_id == PERSON_CLASS_ID and conf >= settings.YOLO_CONFIDENCE_THRESHOLD:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        detections.append(((x1, y1, x2, y2), conf))
            except Exception as e:
                logger.error(f"Error during YOLOv8 detection: {e}")
        else:
            # Fallback mock detections based on simple motion or contour detection if needed,
            # or return empty list for simulation control.
            pass
        return detections

    def extract_reid_features(self, crop: np.ndarray) -> np.ndarray:
        """
        Extracts Re-ID embedding vector (512-dim) using a deep representation network.
        For production, this uses OSNet. We simulate/fallback to histogram + average color descriptor.
        """
        # Ensure crop is valid
        if crop is None or crop.size == 0:
            return np.zeros(512, dtype=np.float32)
        
        # OSNet feature extraction placeholder/simulation
        # Real extraction:
        # tensor = preprocess(crop)
        # embedding = osnet_model(tensor)
        # return embedding.numpy()
        
        # High fidelity simulation of a Re-ID embedding using HSV histogram + resize:
        try:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
            cv2.normalize(hist, hist)
            flat_hist = hist.flatten()
            
            # Pad to 512 dimensions for consistency
            features = np.zeros(512, dtype=np.float32)
            features[:len(flat_hist)] = flat_hist
            return features
        except Exception:
            return np.random.randn(512).astype(np.float32)

    def is_staff(self, feature_vector: np.ndarray) -> bool:
        """
        Compares visitor embedding with staff features DB using Cosine Similarity.
        """
        if not self.staff_feature_db or feature_vector is None:
            return False
        
        # Calculate Cosine Similarity against all registered staff
        for staff_feat in self.staff_feature_db:
            similarity = np.dot(feature_vector, staff_feat) / (
                np.linalg.norm(feature_vector) * np.linalg.norm(staff_feat) + 1e-8
            )
            if similarity >= settings.STAFF_REID_THRESHOLD:
                return True
        return False

    def add_staff_feature(self, feature_vector: np.ndarray):
        """
        Registers a new staff member feature profile.
        """
        self.staff_feature_db.append(feature_vector)

    def map_to_zone(self, bbox: Tuple[int, int, int, int], zone_polygons: Dict[str, np.ndarray]) -> Optional[str]:
        """
        Performs zone mapping for a visitor.
        Calculates center bottom point of bbox (foot level) and performs OpenCV pointPolygonTest.
        """
        x1, y1, x2, y2 = bbox
        center_bottom = (int((x1 + x2) / 2), int(y2))
        
        for zone_name, polygon in zone_polygons.items():
            # pointPolygonTest returns >= 0 if inside or on edge
            dist = cv2.pointPolygonTest(polygon, center_bottom, False)
            if dist >= 0:
                return zone_name
        return None

# Singleton instance
cv_pipeline = CVInferencePipeline()

# PROMPT: Implement final computer vision orchestrator pipeline loop with visual feedback
# CHANGES MADE: Created run_pipeline.py orchestrating detector, tracker, reid, zones, queue, and emitter with OpenCV drawing

import cv2
import numpy as np
import logging
import argparse
import time
from datetime import datetime, timezone
from detect import PersonDetector
from tracker import ObjectTracker
from reid import ReIDMatcher
from zones import ZoneManager
from queue_detector import QueueDetector
from emit import EventEmitter

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pipeline.runner")

# Default Mumbai store zones configurations (from database seed data)
MUMBAI_ZONES = {
    "Entrance Zone": [[0, 0], [100, 0], [100, 100], [0, 100]],
    "Cosmetics Section": [[100, 0], [200, 0], [200, 100], [100, 100]],
    "Billing Queue Zone": [[200, 0], [300, 0], [300, 100], [200, 100]],
    "Skin Care Section": [[0, 100], [100, 100], [100, 200], [0, 200]]
}

def draw_visuals(frame: np.ndarray, tracks: list, zones_manager: ZoneManager, frame_id: int):
    """Draws bounding boxes, labels, and zone boundaries on the visual frame."""
    # 1. Draw store zones as transparent overlays
    overlay = frame.copy()
    colors = {
        "Entrance Zone": (0, 255, 0),      # Green
        "Cosmetics Section": (255, 0, 255), # Magenta
        "Billing Queue Zone": (0, 0, 255),  # Red
        "Skin Care Section": (255, 255, 0)  # Cyan
    }

    for zone_id, poly in zones_manager.zones.items():
        color = colors.get(zone_id, (255, 255, 255))
        # Scaled up for standard 640x480 rendering
        scale_poly = poly * 2
        cv2.polylines(overlay, [scale_poly], isClosed=True, color=color, thickness=2)
        cv2.fillPoly(overlay, [scale_poly], color=tuple(c // 4 for c in color))
        # Draw label
        cv2.putText(overlay, zone_id, (scale_poly[0][0] + 5, scale_poly[0][1] + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    # Blend overlays
    cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    # 2. Draw tracks
    for track in tracks:
        # Scaled coordinates for visualization (detector operates in 320x240 scale space, scaled up to 640x480 here)
        x1, y1, x2, y2 = [coord * 2 for coord in track["bbox"]]
        track_id = track["track_id"]
        v_id = track.get("sim_visitor_id") or f"track-{track_id}"
        
        # Color: green for staff, blue for visitor
        is_staff = "staff" in v_id
        color = (0, 200, 0) if is_staff else (255, 100, 0)
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{v_id} ({track['confidence']:.2f})"
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
        
        # Draw feet center-bottom point
        feet_pt = (int((x1 + x2) / 2), int(y2))
        cv2.circle(frame, feet_pt, 4, (0, 255, 255), -1)

    # 3. Info overlay
    cv2.putText(frame, f"Frame: {frame_id} | Tracks: {len(tracks)}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return frame

def run_pipeline(source: str, store_id: str, camera_id: str, emit_url: str, show_gui: bool):
    logger.info(f"Initializing CV Platform Pipeline for store: {store_id}, camera: {camera_id}...")
    
    # 1. Initialize modules
    detector = PersonDetector(confidence_threshold=0.45)
    tracker = ObjectTracker()
    reid = ReIDMatcher()
    
    # Register dummy staff features
    dummy_staff_emb = np.random.randn(512).astype(np.float32)
    reid.register_staff_vector("staff-01", dummy_staff_emb)
    
    zones_manager = ZoneManager(MUMBAI_ZONES)
    queue_detector = QueueDetector()
    emitter = EventEmitter(api_url=emit_url)

    # 2. Capture source
    # If source is mock or empty, generate a synthetic feed
    is_mock = source.lower() == "mock" or not source
    if not is_mock:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error(f"Could not open video source: {source}. Falling back to simulation.")
            is_mock = True
            
    frame_id = 0
    fps = 30
    frame_w, frame_h = 640, 480
    
    logger.info("Pipeline starting main processing loop. Press Ctrl+C to terminate.")

    try:
        while True:
            t_start = time.time()
            timestamp = datetime.now(timezone.utc)
            
            # Get frame
            if is_mock:
                # Generate black base frame
                frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
                # Draw grid lines for store blueprint representation
                for x in range(0, frame_w, 40):
                    cv2.line(frame, (x, 0), (x, frame_h), (20, 20, 20), 1)
                for y in range(0, frame_h, 40):
                    cv2.line(frame, (0, y), (frame_w, y), (20, 20, 20), 1)
            else:
                ret, frame = cap.read()
                if not ret:
                    logger.info("Video feed completed or lost. Re-winding...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                frame = cv2.resize(frame, (frame_w, frame_h))

            # Run detection (resize to 320x240 to match detector resolution coordinate space)
            small_frame = cv2.resize(frame, (320, 240))
            detections = detector.detect(small_frame, frame_id=frame_id)
            
            # Run tracker
            active_tracks = tracker.update(detections)
            
            # Process track matching and zone routing
            current_active_visitor_zones = {}
            events_to_emit = []

            for track in active_tracks:
                track_id = track["track_id"]
                bbox = track["bbox"]
                
                # Resolve unique identity via Re-ID
                # Crop person image for Re-ID embedding extraction
                x1, y1, x2, y2 = bbox
                # Safeguard boundaries
                y1, y2 = max(0, y1), min(240, y2)
                x1, x2 = max(0, x1), min(320, x2)
                crop = small_frame[y1:y2, x1:x2]
                
                # If mock detector already assigned an identity, reuse it for visual consistency
                if track.get("sim_visitor_id"):
                    visitor_id = track["sim_visitor_id"]
                    is_staff = "staff" in visitor_id
                    sim_score = 1.0
                else:
                    emb = reid.extract_features(crop)
                    visitor_id, is_staff, sim_score = reid.match_visitor(emb)
                
                track["sim_visitor_id"] = visitor_id
                
                # Map coordinate to zone
                x1, y1, x2, y2 = bbox
                foot_point = (int((x1 + x2) / 2), int(y2))
                zone_id = zones_manager.get_zone_at_point(foot_point)
                
                if zone_id:
                    current_active_visitor_zones[visitor_id] = zone_id

                # Generate ZONE_ENTER / ZONE_EXIT events
                zone_events = zones_manager.update_visitor_zone(visitor_id, bbox, timestamp)
                for ze in zone_events:
                    # Format for API ingest schema
                    payload = {
                        "event_id": str(np.random.randint(1e9)),  # auto generated
                        "store_id": store_id,
                        "camera_id": camera_id,
                        "visitor_id": visitor_id,
                        "event_type": ze["event_type"],
                        "timestamp": timestamp,
                        "zone_id": ze["zone_id"],
                        "dwell_ms": ze["dwell_ms"],
                        "is_staff": is_staff,
                        "confidence": track["confidence"],
                        "metadata": {"reid_similarity": sim_score}
                    }
                    events_to_emit.append(payload)
                    
                    # Feed zone transition events to Queue Detector
                    queue_events = queue_detector.process_zone_event(ze, timestamp)
                    for qe in queue_events:
                        events_to_emit.append({
                            "store_id": store_id,
                            "camera_id": camera_id,
                            "visitor_id": visitor_id,
                            "event_type": qe["event_type"],
                            "timestamp": timestamp,
                            "zone_id": ze["zone_id"],
                            "dwell_ms": 0,
                            "is_staff": is_staff,
                            "confidence": track["confidence"],
                            "metadata": qe.get("metadata", {})
                        })

            # Check queue occupancy dwell metrics periodically
            queue_ticks = queue_detector.check_queue_ticks(current_active_visitor_zones, timestamp)
            for qe in queue_ticks:
                events_to_emit.append({
                    "store_id": store_id,
                    "camera_id": camera_id,
                    "visitor_id": qe["visitor_id"],
                    "event_type": qe["event_type"],
                    "timestamp": timestamp,
                    "zone_id": "Billing Queue Zone",
                    "dwell_ms": 0,
                    "is_staff": "staff" in qe["visitor_id"],
                    "confidence": 0.9,
                    "metadata": qe.get("metadata", {})
                })

            # Handle visitors who left the frame (cleanup zone manager state and trigger ZONE_EXIT)
            all_active_visitor_ids = {t.get("sim_visitor_id") for t in active_tracks if t.get("sim_visitor_id")}
            for prev_visitor_id in list(zones_manager.visitor_zone_states.keys()):
                if prev_visitor_id not in all_active_visitor_ids:
                    # Visitor exited frame
                    exit_events = zones_manager.handle_visitor_exit(prev_visitor_id, timestamp)
                    for ee in exit_events:
                        events_to_emit.append({
                            "store_id": store_id,
                            "camera_id": camera_id,
                            "visitor_id": prev_visitor_id,
                            "event_type": ee["event_type"],
                            "timestamp": timestamp,
                            "zone_id": ee["zone_id"],
                            "dwell_ms": ee["dwell_ms"],
                            "is_staff": "staff" in prev_visitor_id,
                            "confidence": 0.9,
                            "metadata": {}
                        })
                        # Also emit main store EXIT event
                        events_to_emit.append({
                            "store_id": store_id,
                            "camera_id": camera_id,
                            "visitor_id": prev_visitor_id,
                            "event_type": "EXIT",
                            "timestamp": timestamp,
                            "zone_id": None,
                            "dwell_ms": ee["dwell_ms"],
                            "is_staff": "staff" in prev_visitor_id,
                            "confidence": 0.9,
                            "metadata": {}
                        })
                
            # If a visitor enters for the first time, emit an ENTRY event
            for track in active_tracks:
                if track["is_new"] and track.get("sim_visitor_id"):
                    events_to_emit.append({
                        "store_id": store_id,
                        "camera_id": camera_id,
                        "visitor_id": track["sim_visitor_id"],
                        "event_type": "ENTRY",
                        "timestamp": timestamp,
                        "zone_id": None,
                        "dwell_ms": 0,
                        "is_staff": "staff" in track["sim_visitor_id"],
                        "confidence": track["confidence"],
                        "metadata": {}
                    })

            # Emit all events batch
            if events_to_emit:
                # We emit events batch to the backend
                # (Note: we support single emit fallback inside emit.py)
                emitter.emit_batch(events_to_emit)

            # Draw visuals
            frame = draw_visuals(frame, active_tracks, zones_manager, frame_id)
            
            if show_gui:
                cv2.imshow("Purplle Store Intelligence - Camera Feed View", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("GUI window closed by user.")
                    break

            # Frame rate limiter
            elapsed = time.time() - t_start
            delay = max(1.0 / fps - elapsed, 0)
            time.sleep(delay)
            
            frame_id += 1
            
    except KeyboardInterrupt:
        logger.info("Pipeline runner terminated by user keyboard interrupt.")
    finally:
        if not is_mock:
            cap.release()
        if show_gui:
            cv2.destroyAllWindows()
        logger.info("Pipeline cleaned up and closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purplle Store Intelligence Camera Inference Pipeline")
    parser.add_argument("--source", type=str, default="mock", help="Video file path or 'mock'")
    parser.add_argument("--store_id", type=str, default="store-mumbai-01", help="Target store id")
    parser.add_argument("--camera_id", type=str, default="cam-cosmetics-01", help="Target camera id")
    parser.add_argument("--emit_url", type=str, default="http://localhost:8000/api/v1/events/ingest", help="Ingest URL")
    parser.add_argument("--gui", action="store_true", help="Display visual cv2 window feed")
    
    args = parser.parse_args()
    
    run_pipeline(
        source=args.source,
        store_id=args.store_id,
        camera_id=args.camera_id,
        emit_url=args.emit_url,
        show_gui=args.gui
    )

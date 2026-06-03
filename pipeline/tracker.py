# PROMPT: Implement production-ready tracker wrapping ByteTrack concepts
# CHANGES MADE: Created tracker.py implementing an IoU tracker with track lifecycle management (active, buffered, stale)

import numpy as np
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("pipeline.tracker")

def calculate_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

class ObjectTracker:
    def __init__(self, max_lost_frames: int = 30, iou_threshold: float = 0.3):
        self.max_lost_frames = max_lost_frames
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, Dict[str, Any]] = {}  # track_id -> track_info
        self.next_track_id = 1

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Updates the tracker with new detections.
        Each detection is: {"bbox": (x1, y1, x2, y2), "confidence": float}
        Returns list of active tracks: {"track_id": int, "bbox": (x1, y1, x2, y2), "confidence": float, "is_new": bool, "sim_visitor_id": str (optional)}
        """
        # Increment lost frame count for all existing tracks
        for track_id in self.tracks:
            self.tracks[track_id]["lost_frames"] += 1

        matched_detections = set()
        matched_tracks = set()

        # Match current detections with existing tracks using IoU
        if self.tracks and detections:
            track_ids = list(self.tracks.keys())
            iou_matrix = np.zeros((len(detections), len(track_ids)), dtype=np.float32)

            for d_idx, det in enumerate(detections):
                for t_idx, t_id in enumerate(track_ids):
                    iou_matrix[d_idx, t_idx] = calculate_iou(det["bbox"], self.tracks[t_id]["bbox"])

            # Greedy matching based on IoU threshold
            while True:
                max_val = np.max(iou_matrix)
                if max_val < self.iou_threshold:
                    break

                d_idx, t_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                t_id = track_ids[t_idx]

                if d_idx not in matched_detections and t_id not in matched_tracks:
                    matched_detections.add(d_idx)
                    matched_tracks.add(t_id)

                    # Update track info
                    self.tracks[t_id]["bbox"] = detections[d_idx]["bbox"]
                    self.tracks[t_id]["confidence"] = detections[d_idx]["confidence"]
                    self.tracks[t_id]["lost_frames"] = 0
                    if "sim_visitor_id" in detections[d_idx]:
                        self.tracks[t_id]["sim_visitor_id"] = detections[d_idx]["sim_visitor_id"]

                # Zero out the row and col so they are not matched again
                iou_matrix[d_idx, :] = -1.0
                iou_matrix[:, t_idx] = -1.0

        # Handle unmatched detections -> Create new tracks
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_detections:
                # If mock detector already supplied a visitor ID, try using that or generating a new track id
                t_id = self.next_track_id
                self.next_track_id += 1
                
                self.tracks[t_id] = {
                    "bbox": det["bbox"],
                    "confidence": det["confidence"],
                    "lost_frames": 0,
                    "is_new": True,
                    "sim_visitor_id": det.get("sim_visitor_id")
                }
                matched_tracks.add(t_id)
            else:
                # Resolve matched track to turn off "is_new" after first frame
                for t_id in self.tracks:
                    if self.tracks[t_id]["lost_frames"] == 0 and t_id in matched_tracks:
                        self.tracks[t_id]["is_new"] = False

        # Clean up stale/lost tracks exceeding max_lost_frames
        tracks_to_delete = []
        for t_id, track in list(self.tracks.items()):
            if track["lost_frames"] > self.max_lost_frames:
                tracks_to_delete.append(t_id)

        for t_id in tracks_to_delete:
            del self.tracks[t_id]
            logger.info(f"Terminated Track ID: {t_id} due to occlusion/exit.")

        # Return list of currently active tracks (lost_frames == 0)
        active_tracks = []
        for t_id, track in self.tracks.items():
            if track["lost_frames"] == 0:
                active_tracks.append({
                    "track_id": t_id,
                    "bbox": track["bbox"],
                    "confidence": track["confidence"],
                    "is_new": track["is_new"],
                    "sim_visitor_id": track.get("sim_visitor_id")
                })
        return active_tracks

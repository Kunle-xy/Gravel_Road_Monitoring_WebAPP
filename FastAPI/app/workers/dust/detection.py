"""
Dust detection module — YOLOv8 vehicle detection within a road polygon.
"""

import cv2 as cv
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Lazy-load YOLO model (loaded once per worker process)
_model = None

VEHICLE_CLASSES = {"car", "truck", "bus"}


def get_yolo_model():
    """Load YOLOv8 model once, reuse across frames."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        import torch
        _model = YOLO("yolov8l.pt")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model.to(device)
        logger.info(f"YOLOv8 model loaded on {device}")
    return _model


def detect_vehicles_in_frame(frame: np.ndarray, polygon: np.ndarray) -> dict:
    """
    Detect vehicles in a single frame within the road polygon.

    Args:
        frame: BGR image (numpy array)
        polygon: Road polygon as np.int32 array of shape (4, 2)

    Returns:
        dict with:
            truck_detected: bool
            vehicles: list of {label, confidence, bbox, inside_polygon}
    """
    model = get_yolo_model()
    results = model.predict(source=frame, conf=0.05, imgsz=960, verbose=False)

    vehicles_found = []
    truck_detected = False

    if results[0].boxes is not None and results[0].boxes.data is not None:
        boxes = results[0].boxes.xyxy
        class_indices = results[0].boxes.cls
        confidences = results[0].boxes.conf
        class_names = model.names

        for box, cls_idx, conf in zip(boxes, class_indices, confidences):
            label = class_names[int(cls_idx)]
            if label not in VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.tolist())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            inside = cv.pointPolygonTest(polygon, (cx, cy), False) >= 0

            vehicles_found.append({
                "label": label,
                "confidence": round(float(conf), 3),
                "bbox": [x1, y1, x2, y2],
                "inside_polygon": inside,
            })

            if inside:
                truck_detected = True

    return {
        "truck_detected": truck_detected,
        "vehicles": vehicles_found,
    }

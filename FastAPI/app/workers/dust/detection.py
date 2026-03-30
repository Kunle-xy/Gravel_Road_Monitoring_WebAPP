"""
YOLO object detection within a bounded road polygon.
Supports multiple model variants.
"""

import cv2 as cv
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Cache loaded models by name
_models: dict = {}

AVAILABLE_MODELS = {
    "yolov8n": {"file": "yolov8n.pt", "label": "YOLOv8 Nano", "desc": "Fastest, lower accuracy"},
    "yolov8s": {"file": "yolov8s.pt", "label": "YOLOv8 Small", "desc": "Fast, good accuracy"},
    "yolov8m": {"file": "yolov8m.pt", "label": "YOLOv8 Medium", "desc": "Balanced speed/accuracy"},
    "yolov8l": {"file": "yolov8l.pt", "label": "YOLOv8 Large", "desc": "Slower, high accuracy"},
    "yolo11l": {"file": "yolo11l.pt", "label": "YOLO11 Large", "desc": "Latest, best accuracy"},
}


def get_yolo_model(model_name: str = "yolov8s"):
    """Load a YOLO model by name, cache for reuse."""
    global _models
    if model_name not in _models:
        from ultralytics import YOLO
        import torch
        model_info = AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["yolov8s"])
        _models[model_name] = YOLO(model_info["file"])
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _models[model_name].to(device)
        logger.info(f"{model_info['label']} loaded on {device}")
    return _models[model_name]


def detect_and_annotate(frame: np.ndarray, polygon: np.ndarray, model_name: str = "yolov8s") -> np.ndarray:
    """
    Run YOLOv8 on a frame, draw bounding boxes for objects inside the polygon.
    Returns the annotated frame.
    """
    model = get_yolo_model(model_name)
    results = model.predict(source=frame, conf=0.25, imgsz=640, verbose=False)

    # Draw polygon overlay (cyan)
    overlay = frame.copy()
    cv.fillPoly(overlay, [polygon], (255, 255, 0))
    cv.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
    cv.polylines(frame, [polygon], True, (255, 255, 0), 2)

    if results[0].boxes is None or results[0].boxes.data is None:
        return frame

    boxes = results[0].boxes.xyxy
    class_indices = results[0].boxes.cls
    confidences = results[0].boxes.conf
    class_names = model.names

    # Color palette for different classes
    colors = [
        (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (128, 255, 0), (255, 128, 0),
    ]

    for box, cls_idx, conf in zip(boxes, class_indices, confidences):
        x1, y1, x2, y2 = map(int, box.tolist())
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # Only annotate objects inside the polygon
        if cv.pointPolygonTest(polygon, (cx, cy), False) < 0:
            continue

        label = class_names[int(cls_idx)]
        color = colors[int(cls_idx) % len(colors)]

        # Bounding box
        cv.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label background
        text = f"{label} {conf:.2f}"
        (tw, th), _ = cv.getTextSize(text, cv.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
        cv.putText(frame, text, (x1 + 2, y1 - 4),
                   cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv.LINE_AA)

    return frame

"""
YOLO object detection within a bounded road polygon.
Uses YOLO26-Large for detection, ResNet-152 for dust classification.
"""

import os
import cv2 as cv
import numpy as np
import logging

logger = logging.getLogger(__name__)

_model = None
_dust_model = None

MODEL_FILE = "yolo26l.pt"
MODEL_LABEL = "YOLO26"

DUST_MODEL_PATH = os.path.join(os.path.dirname(__file__), "best_model_final.pt")
DUST_CLASSES = ["No Dust", "Low Dust", "High Dust"]
VEHICLE_CLASSES = {"car", "truck", "bus"}
TARGET = 224
PADDING = 10


def get_yolo_model():
    """Load the YOLO model, cache for reuse."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        import torch
        _model = YOLO(MODEL_FILE)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model.to(device)
        logger.info(f"{MODEL_LABEL} loaded on {device}")
    return _model


def get_dust_classifier():
    """Load the ResNet-152 dust classification model, cache for reuse."""
    global _dust_model
    if _dust_model is None:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        class RGBCNN(nn.Module):
            def __init__(self, num_classes=3, freeze_backbone=True, dropout=0.3, hidden_size=512):
                super().__init__()
                self.model = models.resnet152(weights=None)
                in_features = self.model.fc.in_features
                self.model.fc = nn.Sequential(
                    nn.Linear(in_features, hidden_size),
                    nn.BatchNorm1d(hidden_size),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.BatchNorm1d(hidden_size // 2),
                    nn.ReLU(),
                    nn.Dropout(dropout / 2),
                    nn.Linear(hidden_size // 2, num_classes),
                )

            def forward(self, x):
                return self.model(x)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = RGBCNN(num_classes=3)
        state = torch.load(DUST_MODEL_PATH, map_location=device, weights_only=True)
        model.load_state_dict(state)
        model.to(device)
        model.eval()
        _dust_model = (model, device)
        logger.info(f"Dust classifier loaded on {device}")
    return _dust_model


def classify_dust(crop_bgr: np.ndarray) -> int:
    """Classify a 224x224 BGR crop. Returns class index (0=High, 1=Low, 2=Non)."""
    import torch
    from torchvision import transforms

    model, device = get_dust_classifier()
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    rgb = cv.cvtColor(crop_bgr, cv.COLOR_BGR2RGB)
    tensor = transform(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        pred = model(tensor).argmax(dim=1).item()
    return pred


def center_square_from_frame(frame: np.ndarray, cx: int, cy: int, side: int) -> np.ndarray:
    """Crop a square region centered on (cx, cy) with padding."""
    H, W = frame.shape[:2]
    padded_side = min(side + 2 * PADDING, H, W)
    x1 = max(0, min(int(round(cx - padded_side / 2)), W - padded_side))
    y1 = max(0, min(int(round(cy - padded_side / 2)), H - padded_side))
    return frame[y1:y1 + padded_side, x1:x1 + padded_side]


def detect_and_annotate(frame: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """
    Run YOLO on a frame, draw bounding boxes for objects inside the polygon.
    Returns the annotated frame.
    """
    model = get_yolo_model()
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

# model.py
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

MODEL_PATH = Path(__file__).with_name("best.engine")

_model = None

def get_model():
    global _model
    if _model is None:
        print(f"Loading {MODEL_PATH} for TensorRT inference...", flush=True)
        _model = YOLO(str(MODEL_PATH), task="detect")
    return _model

def stream(frame: np.ndarray):
    mdl = get_model()
    results = mdl(frame, verbose=False)

    cx, cy = -1, -1
    best_conf = 0.0

    if len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confs = results[0].boxes.conf.cpu().numpy()

        best_idx = int(np.argmax(confs))
        x1, y1, x2, y2 = boxes[best_idx].astype(int)

        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        best_conf = float(confs[best_idx])

        cx = int((x1 + x2) // 2)
        cy = int((y1 + y2) // 2)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"drone {best_conf:.2f}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    # ---------------- HUD confidence bar ----------------
    bar_x = 20
    bar_y = 40
    bar_w = 220
    bar_h = 22

    cv2.putText(
        frame,
        f"Confidence: {best_conf:.2f}",
        (bar_x, bar_y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (120, 120, 120), 2)

    filled_w = int(bar_w * max(0.0, min(1.0, best_conf)))
    if filled_w > 0:
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_w, bar_y + bar_h), (0, 255, 0), -1)

    return frame, int(cx), int(cy)

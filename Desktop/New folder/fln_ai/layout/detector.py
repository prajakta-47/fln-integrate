import logging
from pathlib import Path
from typing import Optional

from fln_ai.config import LAYOUT_MODEL, LAYOUT_CONFIDENCE, LAYOUT_MODEL_PATH

logger = logging.getLogger(__name__)


class LayoutDetector:
    """Layout Detection Engine — identifies regions: headers, instructions, questions, pictures, answers.

    Uses DocLayout-YOLO or YOLOv11 when available.
    Falls back to a heuristic-based detector when no model is loaded.
    """

    def __init__(self, model_name: str = LAYOUT_MODEL, model_path: Optional[Path] = None):
        self.model_name = model_name
        self.model_path = model_path or LAYOUT_MODEL_PATH
        self.model = None
        self._load_model()

    def _load_model(self):
        """Attempt to load the YOLO model. Gracefully handle missing dependencies."""
        if not self.model_path.exists():
            logger.warning(
                "Layout model not found at %s. Using heuristic fallback.", self.model_path
            )
            return
        try:
            if self.model_name == "doclayout-yolo":
                from doclayout_yolo import DocLayoutYOLO
                self.model = DocLayoutYOLO(str(self.model_path))
                logger.info("Loaded DocLayout-YOLO from %s", self.model_path)
            else:
                from ultralytics import YOLO
                self.model = YOLO(str(self.model_path))
                logger.info("Loaded YOLO from %s", self.model_path)
        except ImportError as e:
            logger.warning("Layout model dependencies missing (%s). Using heuristic fallback.", e)

    def detect_regions(self, image_path: str | Path) -> list[dict]:
        """Detect document regions. Returns list of {label, confidence, bbox}."""
        if self.model is not None:
            return self._ml_detect(image_path)
        return self._heuristic_detect(image_path)

    def _ml_detect(self, image_path: str | Path) -> list[dict]:
        """Run ML model inference for layout detection."""
        import cv2
        results = self.model.predict(str(image_path), conf=LAYOUT_CONFIDENCE, verbose=False)
        regions = []
        for result in results:
            for box, cls_id, conf in zip(result.boxes.xyxy, result.boxes.cls, result.boxes.conf):
                x1, y1, x2, y2 = map(int, box.tolist())
                label = result.names[int(cls_id)]
                regions.append({
                    "label": label,
                    "confidence": float(conf),
                    "bbox": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                })
        return sorted(regions, key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))

    @staticmethod
    def _heuristic_detect(image_path: str | Path) -> list[dict]:
        """Rule-based layout detection fallback using contour analysis."""
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 4)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = img.shape[:2]
        regions = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            img_area = w * h
            if area < 0.01 * img_area or area > 0.95 * img_area:
                continue
            if bh < 20 or bw < 20:
                continue
            label = self._classify_region(y, bh, h)
            regions.append({
                "label": label,
                "confidence": 0.5,
                "bbox": {"x": x, "y": y, "width": bw, "height": bh},
            })
        return sorted(regions, key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))

    @staticmethod
    def _classify_region(y: int, bh: int, img_h: int) -> str:
        top_ratio = y / img_h
        height_ratio = bh / img_h
        if top_ratio < 0.08 and height_ratio < 0.1:
            return "header"
        if height_ratio > 0.5:
            return "picture"
        if height_ratio > 0.1:
            return "question"
        return "unknown"

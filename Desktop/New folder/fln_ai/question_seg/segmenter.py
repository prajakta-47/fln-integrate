import cv2
import logging
import numpy as np
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fln_ai.config import CROPPED_DIR
from fln_ai.layout.detector import LayoutDetector

logger = logging.getLogger(__name__)


class QuestionSegmenter:
    """Question Segmentation Engine — crops each detected question into an independent image.

    Every question becomes its own crop for downstream Gemma analysis.
    """

    def __init__(self, detector: Optional[LayoutDetector] = None):
        self.detector = detector or LayoutDetector()

    def segment(self, image_path: str | Path, worksheet_id: str = "") -> list[dict]:
        """Detect question regions and crop them into individual images.

        Returns list of {question_id, crop_path, bbox, page_ref}.
        """
        import cv2
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        regions = self.detector.detect_regions(image_path)
        question_regions = [
            r for r in regions
            if r["label"] in ("question", "instruction", "answer")
        ]

        if not question_regions:
            logger.warning("No question regions detected. Falling back to full-image crop.")
            question_regions = [{
                "label": "question",
                "confidence": 1.0,
                "bbox": {"x": 0, "y": 0, "width": img.shape[1], "height": img.shape[0]},
            }]

        crops = []
        for i, region in enumerate(question_regions):
            b = region["bbox"]
            x, y, w, h = b["x"], b["y"], b["width"], b["height"]
            x, y = max(0, x), max(0, y)
            w, h = min(w, img.shape[1] - x), min(h, img.shape[0] - y)

            crop = img[y:y+h, x:x+w]
            if crop.size == 0:
                continue

            qid = f"{worksheet_id or 'ws'}_{uuid4().hex[:8]}_{i:03d}"
            stem = Path(image_path).stem
            crop_dir = Path(CROPPED_DIR) / stem
            crop_dir.mkdir(parents=True, exist_ok=True)
            crop_path = crop_dir / f"{qid}.png"
            cv2.imwrite(str(crop_path), crop)

            crops.append({
                "question_id": qid,
                "worksheet_id": worksheet_id,
                "crop_path": str(crop_path),
                "bbox": b,
                "page_ref": stem,
                "region_label": region["label"],
                "confidence": region["confidence"],
            })

        logger.info("Segmented %d questions from %s", len(crops), image_path)
        return crops

    @staticmethod
    def merge_grouped_questions(crops: list[dict], max_y_gap: int = 30) -> list[dict]:
        """Merge vertically-adjacent crops that likely belong to the same question group."""
        if not crops:
            return []
        sorted_crops = sorted(crops, key=lambda c: (c["bbox"]["y"], c["bbox"]["x"]))
        merged = [sorted_crops[0]]
        for crop in sorted_crops[1:]:
            prev = merged[-1]
            prev_bottom = prev["bbox"]["y"] + prev["bbox"]["height"]
            curr_top = crop["bbox"]["y"]
            if curr_top - prev_bottom < max_y_gap:
                prev["bbox"]["height"] = (
                    crop["bbox"]["y"] + crop["bbox"]["height"] - prev["bbox"]["y"]
                )
                prev["merge_count"] = prev.get("merge_count", 1) + 1
            else:
                merged.append(crop)
        return merged

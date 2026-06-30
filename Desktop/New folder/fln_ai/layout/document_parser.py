import logging
from pathlib import Path
from typing import Optional

from fln_ai.layout.detector import LayoutDetector

logger = logging.getLogger(__name__)


class DocumentParser:
    """Universal Document Parser — structures a worksheet into educational components.

    Identifies:
      - Header (title, metadata)
      - Instructions
      - Question blocks
      - Pictures / illustrations
      - Answer areas
    """

    def __init__(self, detector: Optional[LayoutDetector] = None):
        self.detector = detector or LayoutDetector()

    def parse(self, image_path: str | Path) -> dict:
        """Parse a worksheet image into structured components."""
        regions = self.detector.detect_regions(image_path)
        return {
            "image_path": str(image_path),
            "regions": regions,
            "header": self._filter_regions(regions, "header"),
            "instructions": self._filter_regions(regions, "instruction"),
            "questions": self._filter_regions(regions, "question"),
            "pictures": self._filter_regions(regions, "picture"),
            "answer_areas": self._filter_regions(regions, "answer"),
            "unknown": self._filter_regions(regions, "unknown"),
        }

    @staticmethod
    def _filter_regions(regions: list[dict], label: str) -> list[dict]:
        return [r for r in regions if r["label"] == label]

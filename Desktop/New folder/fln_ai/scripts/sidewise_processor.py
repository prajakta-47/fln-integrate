#!/usr/bin/env python3
"""Sidewise Batch Processor — processes pre-cropped question images organized by level/sub_level.

Input format:
  Side wise/
    ├── 1.0.zip          → Level 1, Sub-level 1.0
    ├── 1.1.zip          → Level 1, Sub-level 1.1
    └── 2.0.zip          → Level 2, Sub-level 2.0
        (each zip contains individual question crop images)

Usage:
    python -m fln_ai.scripts.sidewise_processor --sidewise Side wise
    python -m fln_ai.scripts.sidewise_processor --sidewise Side wise --publisher "ABC Pub"
"""

import argparse
import json
import logging
import sys
import time
import zipfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fln_ai.config import (
    LOGS_DIR, JSON_DIR, REPORTS_DIR,
    CONFIDENCE_AUTO_SAVE, CONFIDENCE_REVIEW,
)
from fln_ai.preprocessing import PreprocessingEngine
from fln_ai.gemma import GemmaLoader, GemmaAnalyzer
from fln_ai.normalization import NormalizationEngine
from fln_ai.difficulty import DifficultyClassifier
from fln_ai.validation import JSONValidator
from fln_ai.database import QuestionRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"sidewise_{time.strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("sidewise")


class SidewiseProcessor:
    """Process pre-cropped question images organized by level/sub_level."""

    def __init__(self, publisher: str = ""):
        self.preprocessor = PreprocessingEngine()
        self.gemma_loader = GemmaLoader()
        self.gemma = None
        self.normalizer = NormalizationEngine()
        self.difficulty = DifficultyClassifier()
        self.validator = JSONValidator()
        self.repository = QuestionRepository()
        self.publisher = publisher
        self.all_results = []
        self.auto_saved = 0
        self.review_count = 0

    def run(self, sidewise_dir: str | Path):
        overall_start = time.time()
        logger.info("=" * 60)
        logger.info("SIDEWISE BATCH PROCESSOR")
        logger.info("=" * 60)

        sidewise_dir = Path(sidewise_dir)
        if not sidewise_dir.exists():
            logger.error("Directory not found: %s", sidewise_dir)
            return

        # Find and extract all zip files
        zip_files = sorted(sidewise_dir.glob("*.zip"))
        if not zip_files:
            logger.error("No zip files found in %s", sidewise_dir)
            return

        logger.info("Found %d zip files: %s", len(zip_files), [z.name for z in zip_files])

        # Load Gemma once
        logger.info("Loading Gemma 4 26B...")
        self.gemma_loader.load()
        self.gemma = GemmaAnalyzer(self.gemma_loader.model)

        for zip_path in zip_files:
            self._process_zip(zip_path)

        # Final export
        self._finalize()

        elapsed = (time.time() - overall_start) / 60
        logger.info("\nTotal: %d questions in %.1f min", len(self.all_results), elapsed)
        logger.info("Auto-saved: %d | Review needed: %d", self.auto_saved, self.review_count)

    def _process_zip(self, zip_path: Path):
        """Extract and process one zip file (one level/sub_level)."""
        stem = zip_path.stem  # e.g. "1.0"
        parts = stem.split(".")
        level = parts[0] if len(parts) > 0 else ""
        sub_level = stem if len(parts) > 1 else ""

        logger.info("\n─── Processing: %s (Level %s, Sub-level %s) ───", zip_path.name, level, sub_level)

        # Extract to temp directory
        extract_dir = Path(zip_path.parent) / f".extracted_{stem}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)

        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)

        # Collect images (handle nested folders)
        image_paths = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff"):
            image_paths.extend(sorted(extract_dir.rglob(ext)))

        logger.info("  Images found: %d", len(image_paths))

        for img_path in image_paths:
            self._process_image(img_path, level, sub_level, zip_path.stem)

        # Cleanup temp extraction
        shutil.rmtree(extract_dir)

    def _process_image(self, img_path: Path, level: str, sub_level: str, worksheet_id: str):
        """Analyze a single cropped question image."""
        logger.info("    Analyzing: %s", img_path.name)

        # Preprocess
        try:
            img, info = PreprocessingEngine.process_file(img_path)
        except ValueError as e:
            logger.warning("      Skip: %s", e)
            return

        # Gemma: Question analysis
        q_result = self.gemma.analyze_question(img)
        q_data = q_result.get("parsed") or {}

        # Gemma: Difficulty
        d_result = self.gemma.classify_difficulty(img)
        difficulty = self.difficulty.from_gemma(d_result)

        # Gemma: Illustration
        i_result = self.gemma.understand_illustration(img)
        i_data = i_result.get("parsed") or {}

        # Build final record
        record = {
            "question_id": f"{worksheet_id}_{img_path.stem}",
            "level": level,
            "sub_level": sub_level,
            "worksheet_id": worksheet_id,
            "publisher": self.publisher,
            "concept": q_data.get("educational_concept", ""),
            "learning_outcome": q_data.get("learning_outcome", ""),
            "question_type": q_data.get("question_type", ""),
            "instruction": "",
            "question_text": "",
            "illustration": {
                "objects": i_data.get("objects", []),
                "count": i_data.get("count", 0),
                "arrangement": i_data.get("arrangement", ""),
                "purpose": i_data.get("educational_purpose", ""),
            },
            "difficulty": difficulty,
            "expected_answer": q_data.get("expected_answer", ""),
            "skills": q_data.get("skills", []),
            "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0},
            "confidence": float(q_data.get("confidence_score", 0.7)),
        }

        # Normalize
        normalized = self.normalizer.normalize_question(record)

        # Validate
        final = JSONValidator.validate(normalized)

        # Save / Review decision
        decision = self.repository.auto_or_review(final)
        self.all_results.append(final)
        if decision == "auto_saved":
            self.auto_saved += 1
        else:
            self.review_count += 1

    def _finalize(self):
        if not self.all_results:
            logger.warning("No results.")
            return

        kb_path = self.repository.export_knowledge_base()
        rq_path = self.repository.export_review_queue()
        stats = self.repository.stats()

        report = {
            "total_questions": len(self.all_results),
            "auto_saved": self.auto_saved,
            "needs_review": self.review_count,
            "avg_confidence": stats.get("avg_confidence", 0),
            "by_type": stats.get("by_type", {}),
        }
        report_path = REPORTS_DIR / f"sidewise_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info("Knowledge base: %s (%d questions)", kb_path, len(self.all_results))
        logger.info("Report: %s", report_path)


def main():
    parser = argparse.ArgumentParser(description="Sidewise Batch Processor for pre-cropped FLN questions")
    parser.add_argument("--sidewise", "-s", default="Side wise",
                        help="Path to Side wise directory containing level zip files")
    parser.add_argument("--publisher", "-p", default="", help="Publisher name (optional)")
    args = parser.parse_args()

    processor = SidewiseProcessor(publisher=args.publisher)
    processor.run(args.sidewise)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Phase 1 Pipeline Orchestrator — converts heterogeneous worksheets into a standardized Question Knowledge Base.

Usage:
    python -m fln_ai.scripts.run_pipeline --input /path/to/worksheets
    python -m fln_ai.scripts.run_pipeline --input /path/to/worksheets --publisher "ABC Publications"
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fln_ai.config import (
    RAW_DIR, PROCESSED_DIR, CROPPED_DIR, JSON_DIR, LOGS_DIR, REPORTS_DIR,
    CONFIDENCE_AUTO_SAVE,
)
from fln_ai.dataset import DatasetManager
from fln_ai.preprocessing import PreprocessingEngine
from fln_ai.layout import DocumentParser
from fln_ai.question_seg import QuestionSegmenter
from fln_ai.gemma import GemmaLoader, GemmaAnalyzer
from fln_ai.normalization import NormalizationEngine
from fln_ai.difficulty import DifficultyClassifier
from fln_ai.validation import JSONValidator
from fln_ai.database import QuestionRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"pipeline_{time.strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pipeline")


class Phase1Pipeline:
    """End-to-end Phase 1 pipeline."""

    def __init__(self, publisher: str = ""):
        self.dataset = DatasetManager()
        self.preprocessor = PreprocessingEngine()
        self.doc_parser = DocumentParser()
        self.segmenter = QuestionSegmenter()
        self.gemma_loader = GemmaLoader()
        self.gemma = None
        self.normalizer = NormalizationEngine()
        self.difficulty = DifficultyClassifier()
        self.validator = JSONValidator()
        self.repository = QuestionRepository()
        self.worksheet_id = ""
        self.results = []
        self.auto_saved = 0
        self.review_count = 0

    def run(self, input_path: str, publisher: str = ""):
        """Execute full Phase 1 pipeline."""
        overall_start = time.time()
        logger.info("=" * 60)
        logger.info("PHASE 1: Educational Knowledge Extraction Engine")
        logger.info("=" * 60)
        logger.info("Input: %s", input_path)

        # 1. Dataset Management
        logger.info("\n─── Stage 1: Dataset Ingestion ───")
        records = self._stage1_ingest(input_path, publisher)

        if not records:
            logger.warning("No valid images found. Pipeline aborted.")
            return

        # 2. Load Gemma
        logger.info("\n─── Stage 2: Loading Gemma 4 26B ───")
        self.gemma_loader.load()
        self.gemma = GemmaAnalyzer(self.gemma_loader.model)

        # 3. Process each image
        for idx, record in enumerate(records):
            logger.info("\n─── Stage 3: Processing image %d/%d ───", idx + 1, len(records))
            self._process_image(record, idx, len(records))

        # 4. Save knowledge base
        logger.info("\n─── Stage Final: Knowledge Base Export ───")
        self._finalize()

        elapsed = (time.time() - overall_start) / 60
        logger.info("\nPipeline completed in %.1f minutes", elapsed)
        logger.info("Questions extracted: %d", len(self.results))
        logger.info("Auto-saved: %d | Review needed: %d", self.auto_saved, self.review_count)

    def _stage1_ingest(self, input_path: str, publisher: str) -> list[Path]:
        input_path = Path(input_path)
        if not input_path.exists():
            logger.error("Input path does not exist: %s", input_path)
            return []

        self.dataset.ingest_path(input_path)
        self.worksheet_id = self.dataset.assign_metadata(publisher=publisher)["worksheet_id"]

        logger.info("Validating images...")
        validation = self.dataset.validate_images()
        valid_count = sum(1 for v in validation if v["valid"])
        logger.info("Valid images: %d/%d", valid_count, len(validation))

        dups = self.dataset.remove_duplicates()
        if dups:
            logger.info("Duplicates removed: %d", len(dups))

        staged = self.dataset.stage_processed()
        logger.info("Staged for processing: %d files", len(staged))
        return staged

    def _process_image(self, image_path: Path, idx: int, total: int):
        logger.info("Image: %s", image_path.name)

        # 3a. Preprocess
        try:
            img, preproc_info = PreprocessingEngine.process_file(image_path)
            logger.info("  Preprocessing: %s", ", ".join(preproc_info["applied"]))
        except ValueError as e:
            logger.error("  Failed: %s", e)
            return

        # 3b. Layout detection
        parse_result = self.doc_parser.parse(image_path)
        logger.info("  Regions detected: %d", len(parse_result["regions"]))

        # 3c. Question segmentation
        crops = self.segmenter.segment(image_path, worksheet_id=self.worksheet_id)
        logger.info("  Questions segmented: %d", len(crops))

        # 3d. Gemma analysis per question
        for crop in crops:
            self._analyze_crop(crop, img)

    def _analyze_crop(self, crop: dict, worksheet_img):
        """Run all Gemma analysis prompts on one cropped question."""
        crop_path = crop["crop_path"]
        logger.info("    Analyzing crop: %s", Path(crop_path).name)

        try:
            import cv2
            crop_img = cv2.imread(crop_path)
            if crop_img is None:
                return
            crop_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            logger.warning("    Cannot read crop: %s", e)
            return

        # Prompt 1: Question analysis
        q_result = self.gemma.analyze_question(crop_img)
        q_data = q_result.get("parsed") or {}

        # Prompt 2: Difficulty
        d_result = self.gemma.classify_difficulty(crop_img)
        d_data = d_result.get("parsed") or {}
        difficulty = self.difficulty.from_gemma(d_result)

        # Prompt 3: Illustration understanding
        i_result = self.gemma.understand_illustration(crop_img)
        i_data = i_result.get("parsed") or {}

        # Merge into final normalized record
        base = {
            "question_id": crop["question_id"],
            "level": q_data.get("educational_concept", "").split(" > ")[0] if " > " in q_data.get("educational_concept", "") else "",
            "sub_level": "",
            "worksheet_id": crop.get("worksheet_id", ""),
            "publisher": "",
            "concept": q_data.get("educational_concept", ""),
            "learning_outcome": q_data.get("learning_outcome", ""),
            "question_type": q_data.get("question_type", ""),
            "instruction": "",
            "question_text": q_data.get("expected_answer", ""),
            "illustration": {
                "objects": i_data.get("objects", []),
                "count": i_data.get("count", 0),
                "arrangement": i_data.get("arrangement", ""),
                "purpose": i_data.get("educational_purpose", ""),
            },
            "difficulty": difficulty,
            "expected_answer": q_data.get("expected_answer", ""),
            "skills": q_data.get("skills", []),
            "bounding_box": crop.get("bbox", {"x": 0, "y": 0, "width": 0, "height": 0}),
            "confidence": float(d_data.get("confidence_score", 0.7)),
        }

        # Normalize
        normalized = self.normalizer.normalize_question(base)

        # Validate
        final = JSONValidator.validate(normalized)

        # Save / Review
        decision = self.repository.auto_or_review(final)
        self.results.append(final)
        if decision == "auto_saved":
            self.auto_saved += 1
        else:
            self.review_count += 1

    def _finalize(self):
        if not self.results:
            logger.warning("No results to export.")
            return

        kb_path = self.repository.export_knowledge_base()
        rq_path = self.repository.export_review_queue()

        stats = self.repository.stats()
        report_path = REPORTS_DIR / f"pipeline_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(stats, f, indent=2)
        logger.info("Report saved: %s", report_path)
        logger.info("Knowledge base: %s (%d questions)", kb_path, stats["total"])


def main():
    parser = argparse.ArgumentParser(description="FLN Phase 1 — Educational Knowledge Extraction Engine")
    parser.add_argument("--input", "-i", required=True, help="Path to input file or directory")
    parser.add_argument("--publisher", "-p", default="", help="Publisher name (optional)")
    args = parser.parse_args()

    pipeline = Phase1Pipeline()
    pipeline.run(args.input, args.publisher)


if __name__ == "__main__":
    main()

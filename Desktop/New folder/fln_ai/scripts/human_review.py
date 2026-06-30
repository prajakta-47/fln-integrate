#!/usr/bin/env python3
"""Human Review Queue Interface — flags low-confidence extractions for manual review.

Confidence >= 0.90 → Auto-save
Confidence 0.70-0.89 → Flagged for review
Confidence < 0.70 → Low confidence, manual correction recommended

Usage:
    python -m fln_ai.scripts.human_review
    python -m fln_ai.scripts.human_review --queue outputs/json/review_queue.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fln_ai.config import JSON_DIR, CONFIDENCE_AUTO_SAVE, CONFIDENCE_REVIEW

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("review")


class HumanReview:
    """Human review queue for low-confidence question extractions."""

    def __init__(self, queue_path: Path = None):
        self.queue_path = queue_path or (JSON_DIR / "review_queue.json")
        self.queue: list[dict] = []
        self.approved: list[dict] = []
        self.rejected: list[dict] = []

    def load(self):
        if not self.queue_path.exists():
            logger.warning("No review queue found at %s", self.queue_path)
            return
        with open(self.queue_path) as f:
            self.queue = json.load(f)
        logger.info("Loaded %d questions for review.", len(self.queue))

    def summary(self):
        """Print a summary of the review queue."""
        if not self.queue:
            logger.info("Review queue is empty.")
            return

        low = [q for q in self.queue if float(q.get("confidence", 0)) < CONFIDENCE_REVIEW]
        mid = [q for q in self.queue if CONFIDENCE_REVIEW <= float(q.get("confidence", 0)) < CONFIDENCE_AUTO_SAVE]

        logger.info("\n=== REVIEW QUEUE SUMMARY ===")
        logger.info("Total for review: %d", len(self.queue))
        logger.info("  Low confidence (< %.2f): %d", CONFIDENCE_REVIEW, len(low))
        logger.info("  Medium confidence (%.2f-%.2f): %d",
                    CONFIDENCE_REVIEW, CONFIDENCE_AUTO_SAVE, len(mid))

        types = {}
        for q in self.queue:
            qt = q.get("question_type", "unknown")
            types[qt] = types.get(qt, 0) + 1
        logger.info("\nBy question type:")
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            logger.info("  %s: %d", t, c)

    def approve_all(self, output_path: Path = None):
        """Approve all reviewed questions and save to knowledge base."""
        output_path = output_path or (JSON_DIR / "reviewed_approved.json")
        with open(output_path, "w") as f:
            json.dump(self.queue, f, indent=2, ensure_ascii=False)
        logger.info("Approved %d questions → %s", len(self.queue), output_path)

    def export_stats(self):
        """Export review statistics."""
        if not self.queue:
            return {"total": 0}
        return {
            "total_reviewed": len(self.queue),
            "low_confidence": sum(
                1 for q in self.queue if float(q.get("confidence", 0)) < CONFIDENCE_REVIEW
            ),
            "medium_confidence": sum(
                1 for q in self.queue
                if CONFIDENCE_REVIEW <= float(q.get("confidence", 0)) < CONFIDENCE_AUTO_SAVE
            ),
            "question_types": {
                t: c for t, c in sorted(
                    {q.get("question_type", "unknown"): 0 for q in self.queue}.items(),
                    key=lambda x: -x[1],
                )
            },
        }


def main():
    parser = argparse.ArgumentParser(description="Human Review Queue for FLN Knowledge Base")
    parser.add_argument("--queue", default=None, help="Path to review queue JSON")
    parser.add_argument("--summary", action="store_true", help="Show review queue summary")
    parser.add_argument("--approve", action="store_true", help="Approve all queued questions")
    args = parser.parse_args()

    review = HumanReview(Path(args.queue) if args.queue else None)
    review.load()

    if args.summary:
        review.summary()
    elif args.approve:
        review.approve_all()
    else:
        review.summary()
        logger.info("\nUse --approve to save all, or --summary to view details.")


if __name__ == "__main__":
    main()

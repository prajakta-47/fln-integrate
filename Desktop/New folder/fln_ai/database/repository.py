import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fln_ai.config import JSON_DIR, CONFIDENCE_AUTO_SAVE, CONFIDENCE_REVIEW

logger = logging.getLogger(__name__)


class QuestionRepository:
    """Question Knowledge Repository — stores, retrieves, and manages question records.

    Prototype: JSON file-based.
    Future: PostgreSQL.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or JSON_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = []
        self._review_queue: list[dict] = []

    # ── Save ───────────────────────────────────────────────

    def save_question(self, record: dict) -> Path:
        """Save a single question record as JSON."""
        qid = record.get("question_id", "unknown")
        ws = record.get("worksheet_id", "unknown")
        path = self.output_dir / f"{ws}_{qid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        return path

    def save_batch(self, records: list[dict], batch_name: str = "") -> Path:
        """Save all records into a single batch JSON file."""
        if not batch_name:
            batch_name = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = self.output_dir / f"{batch_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d records to %s", len(records), path)
        return path

    def auto_or_review(self, record: dict) -> str:
        """Decision: auto-save or send to review queue based on confidence."""
        confidence = float(record.get("confidence", 0))
        if confidence >= CONFIDENCE_AUTO_SAVE:
            self.save_question(record)
            self._records.append(record)
            return "auto_saved"
        elif confidence >= CONFIDENCE_REVIEW:
            self._review_queue.append(record)
            self.save_question(record)  # still save, but flag for review
            return "saved_for_review"
        else:
            self._review_queue.append(record)
            return "flagged_low_confidence"

    # ── Export ─────────────────────────────────────────────

    def export_knowledge_base(self, path: Optional[Path] = None) -> Path:
        """Export the entire knowledge base as a single JSON file."""
        path = path or (self.output_dir / "knowledge_base.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2, ensure_ascii=False)
        logger.info("Knowledge base exported: %s (%d questions)", path, len(self._records))
        return path

    def export_review_queue(self, path: Optional[Path] = None) -> Path:
        """Export questions needing manual review."""
        path = path or (self.output_dir / "review_queue.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._review_queue, f, indent=2, ensure_ascii=False)
        logger.info("Review queue exported: %s (%d questions)", path, len(self._review_queue))
        return path

    # ── Stats ──────────────────────────────────────────────

    def stats(self) -> dict:
        """Return aggregate statistics about the repository."""
        if not self._records:
            return {"total": 0}
        confs = [float(r.get("confidence", 0)) for r in self._records]
        types = {}
        for r in self._records:
            qt = r.get("question_type", "unknown")
            types[qt] = types.get(qt, 0) + 1
        return {
            "total": len(self._records),
            "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0,
            "auto_saved": sum(1 for c in confs if c >= CONFIDENCE_AUTO_SAVE),
            "needs_review": len(self._review_queue),
            "by_type": types,
        }

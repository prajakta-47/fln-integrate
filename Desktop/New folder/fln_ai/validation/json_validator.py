import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class JSONValidator:
    """JSON Validation Engine — validates and fills missing fields for every question record.

    Final schema requirements:
      question_id, level, sub_level, worksheet_id, publisher, concept,
      learning_outcome, question_type, instruction, question_text,
      illustration (objects, count, arrangement, purpose),
      difficulty, expected_answer, skills, bounding_box, confidence
    """

    REQUIRED_FIELDS = [
        "question_id", "level", "sub_level", "worksheet_id", "publisher",
        "concept", "learning_outcome", "question_type", "instruction",
        "question_text", "illustration", "difficulty", "expected_answer",
        "skills", "bounding_box", "confidence",
    ]

    ILLUSTRATION_FIELDS = ["objects", "count", "arrangement", "purpose"]
    BBOX_FIELDS = ["x", "y", "width", "height"]

    @classmethod
    def validate(cls, record: dict) -> dict:
        """Validate a single question record. Returns the validated record with inferred fields."""
        validated = dict(record)

        for field in cls.REQUIRED_FIELDS:
            if field not in validated or validated[field] is None:
                validated[field] = cls._infer_default(field)

        # Nested: illustration
        if not isinstance(validated.get("illustration"), dict):
            validated["illustration"] = {}
        for f in cls.ILLUSTRATION_FIELDS:
            if f not in validated["illustration"]:
                validated["illustration"][f] = cls._infer_illustration_default(f)

        # Nested: bounding_box
        if not isinstance(validated.get("bounding_box"), dict):
            validated["bounding_box"] = {}
        for f in cls.BBOX_FIELDS:
            if f not in validated["bounding_box"]:
                validated["bounding_box"][f] = 0

        # Ensure skills is a list
        if not isinstance(validated.get("skills"), list):
            validated["skills"] = []

        # Confidence must be float 0-1
        conf = validated.get("confidence", 0.0)
        try:
            conf = float(conf)
        except (ValueError, TypeError):
            conf = 0.0
        validated["confidence"] = max(0.0, min(1.0, conf))

        validated["_validated"] = True
        return validated

    @classmethod
    def batch_validate(cls, records: list[dict]) -> list[dict]:
        """Validate a batch of question records."""
        results = []
        for record in records:
            try:
                results.append(cls.validate(record))
            except Exception as e:
                logger.error("Validation failed for %s: %s",
                             record.get("question_id", "?"), e)
                record["_validation_error"] = str(e)
                results.append(record)
        return results

    @staticmethod
    def _infer_default(field: str):
        defaults = {
            "question_id": "unknown",
            "level": "",
            "sub_level": "",
            "worksheet_id": "",
            "publisher": "unknown",
            "concept": "",
            "learning_outcome": "",
            "question_type": "",
            "instruction": "",
            "question_text": "",
            "illustration": {"objects": [], "count": 0, "arrangement": "", "purpose": ""},
            "difficulty": "medium",
            "expected_answer": "",
            "skills": [],
            "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0},
            "confidence": 0.0,
        }
        return defaults.get(field, "")

    @staticmethod
    def _infer_illustration_default(field: str):
        defaults = {"objects": [], "count": 0, "arrangement": "", "purpose": ""}
        return defaults.get(field, "")

    @classmethod
    def validation_report(cls, records: list[dict]) -> dict:
        """Generate a quality report for a batch of records."""
        total = len(records)
        complete = sum(1 for r in records if r.get("_validated"))
        missing_fields = {}
        for field in cls.REQUIRED_FIELDS:
            count = sum(1 for r in records if not r.get(field))
            if count:
                missing_fields[field] = count

        high_conf = sum(1 for r in records if float(r.get("confidence", 0)) >= 0.9)
        low_conf = sum(1 for r in records if float(r.get("confidence", 0)) < 0.7)

        return {
            "total": total,
            "validated": complete,
            "missing_fields": missing_fields,
            "high_confidence": high_conf,
            "review_recommended": low_conf,
            "auto_save_count": high_conf,
            "manual_review_count": low_conf,
        }

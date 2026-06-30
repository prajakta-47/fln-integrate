import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NormalizationEngine:
    """Educational Normalization Engine — strips publisher-specific styling.

    Ignores fonts, borders, decoration, colors, brand.
    Extracts only the educational knowledge from any worksheet source.
    """

    def __init__(self):
        self._concept_map = self._build_concept_map()

    @staticmethod
    def _build_concept_map() -> dict:
        """Map publisher-specific type labels to normalized FLN concepts."""
        return {
            # Numeracy
            "counting": "Counting",
            "count": "Counting",
            "count and write": "Counting",
            "count the objects": "Counting",
            "number recognition": "Number Recognition",
            "identify the number": "Number Recognition",
            "missing number": "Missing Numbers",
            "what comes after": "Missing Numbers",
            "what comes before": "Missing Numbers",
            "what comes between": "Missing Numbers",
            "ascending": "Ascending Order",
            "descending": "Descending Order",
            "skip count": "Skip Counting",
            "addition": "Addition",
            "add": "Addition",
            "find the sum": "Addition",
            "subtraction": "Subtraction",
            "subtract": "Subtraction",
            "take away": "Subtraction",
            "word problem": "Word Problem",
            "story sum": "Word Problem",
            "shapes": "Shapes",
            "shape": "Shapes",
            "pattern": "Patterns",
            "match": "Matching",
            "match the following": "Matching",
            "comparison": "Comparison",
            "compare": "Comparison",
            "bigger": "Comparison",
            "smaller": "Comparison",
            "taller": "Comparison",
            "shorter": "Comparison",
            "measurement": "Measurement",
            "data handling": "Data Handling",
            "money": "Money",
            "time": "Time",
            "fraction": "Fractions",
            # Literacy
            "letter recognition": "Letter Recognition",
            "alphabet": "Letter Recognition",
            "phonics": "Phonics",
            "sound": "Phonics",
            "vocabulary": "Vocabulary",
            "word meaning": "Vocabulary",
            "reading": "Reading Comprehension",
            "comprehension": "Reading Comprehension",
            "sentence": "Sentence Writing",
            "writing practice": "Writing Practice",
            "trace": "Tracing",
            "tracing": "Tracing",
            "coloring": "Coloring",
            "color": "Coloring",
            # General
            "classification": "Classification",
            "sort": "Classification",
            "logical": "Logical Reasoning",
            "reasoning": "Logical Reasoning",
            "review": "Review Assessment",
            "assessment": "Review Assessment",
        }

    def normalize_question_type(self, raw_type: str) -> str:
        raw_lower = raw_type.strip().lower()
        for key, normalized in self._concept_map.items():
            if key in raw_lower:
                return normalized
        return raw_type

    def normalize_question(self, question_data: dict) -> dict:
        """Normalize a single question record across all fields."""
        normalized = dict(question_data)

        if "question_type" in normalized:
            normalized["question_type"] = self.normalize_question_type(
                normalized["question_type"]
            )

        if "concept" in normalized and normalized["concept"]:
            normalized["concept"] = self.normalize_question_type(normalized["concept"])

        if "difficulty" in normalized:
            normalized["difficulty"] = self._normalize_difficulty(normalized["difficulty"])

        if "skills" in normalized and isinstance(normalized["skills"], list):
            normalized["skills"] = list(set(
                self.normalize_question_type(s) for s in normalized["skills"] if s
            ))

        return normalized

    @staticmethod
    def _normalize_difficulty(raw: str) -> str:
        raw_lower = raw.strip().lower()
        if raw_lower in ("easy", "e", "1", "simple"):
            return "easy"
        if raw_lower in ("medium", "m", "2", "intermediate"):
            return "medium"
        if raw_lower in ("hard", "h", "3", "difficult", "tough"):
            return "hard"
        return raw

    @staticmethod
    def build_final_question(
        question_id: str,
        level: str,
        sub_level: str,
        worksheet_id: str,
        publisher: str,
        concept: str,
        learning_outcome: str,
        question_type: str,
        instruction: str,
        question_text: str,
        illustration: Optional[dict],
        difficulty: str,
        expected_answer: str,
        skills: list,
        bbox: dict,
        confidence: float,
    ) -> dict:
        """Build the standardized final JSON record."""
        return {
            "question_id": question_id,
            "level": level,
            "sub_level": sub_level,
            "worksheet_id": worksheet_id,
            "publisher": publisher,
            "concept": concept,
            "learning_outcome": learning_outcome,
            "question_type": question_type,
            "instruction": instruction,
            "question_text": question_text,
            "illustration": illustration or {
                "objects": [], "count": 0, "arrangement": "", "purpose": "",
            },
            "difficulty": difficulty,
            "expected_answer": expected_answer,
            "skills": skills,
            "bounding_box": bbox,
            "confidence": confidence,
        }

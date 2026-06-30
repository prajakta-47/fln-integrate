import logging

logger = logging.getLogger(__name__)


class DifficultyClassifier:
    """Difficulty Classification Engine — classifies questions as Easy, Medium, or Hard.

    Uses a heuristic scoring system as a fast pre-filter.
    Gemma-based classification (Prompt 3) is the primary method and overrides this.
    """

    FACTORS = {
        "visual_complexity": {"easy": 1, "medium": 2, "hard": 3},
        "reasoning_depth": {"easy": 1, "medium": 2, "hard": 3},
        "working_memory": {"easy": 1, "medium": 2, "hard": 3},
        "pattern_recognition": {"easy": 1, "medium": 2, "hard": 3},
        "counting_complexity": {"easy": 1, "medium": 2, "hard": 3},
        "instruction_complexity": {"easy": 1, "medium": 2, "hard": 3},
        "fine_motor_requirement": {"easy": 1, "medium": 2, "hard": 3},
        "one_to_one_correspondence": {"easy": 1, "medium": 2, "hard": 3},
    }

    @staticmethod
    def heuristic(question_data: dict) -> str:
        """Quick heuristic difficulty estimate based on question metadata."""
        qtype = (question_data.get("question_type") or "").lower()
        num_range = (question_data.get("number_range") or "")
        has_example = question_data.get("has_example", False)

        # Hard types
        hard_types = {"word problem", "logical reasoning", "skip counting",
                      "ascending order", "descending order"}
        if qtype in hard_types:
            return "hard"

        # Medium types
        medium_types = {"addition", "subtraction", "patterns", "comparison",
                        "missing numbers", "classification", "measurement", "time", "money"}
        if qtype in medium_types:
            return "medium"

        # Number-range based
        if num_range:
            try:
                parts = num_range.replace("-", " ").split()
                nums = [int(p) for p in parts if p.isdigit()]
                if nums and max(nums) > 20:
                    return "medium"
            except (ValueError, TypeError):
                pass

        # Example presence
        if not has_example and qtype not in ("coloring", "tracing", "writing practice"):
            return "medium"

        return "easy"

    @staticmethod
    def from_gemma(gemma_result: dict) -> str:
        """Extract difficulty from Gemma's parsed JSON output."""
        if not gemma_result or not isinstance(gemma_result, dict):
            return "unknown"
        parsed = gemma_result.get("parsed") or {}
        diff = parsed.get("difficulty", "")
        if diff.lower() in ("easy", "medium", "hard"):
            return diff.lower()
        return DifficultyClassifier.heuristic(parsed)

    @staticmethod
    def score(question_data: dict) -> dict:
        """Return a detailed difficulty breakdown with scores."""
        diff = DifficultyClassifier.heuristic(question_data)
        base_score = {"easy": 1, "medium": 2, "hard": 3}.get(diff, 2)
        return {
            "overall": diff,
            "score": base_score,
            "max_score": 3,
            "normalized": round(base_score / 3, 2),
        }

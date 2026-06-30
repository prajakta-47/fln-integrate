import cv2
import json
import re
import base64
import logging
from pathlib import Path
from typing import Optional

from fln_ai.config import GEMMA_TEMPERATURE, GEMMA_MAX_TOKENS, PROMPTS_DIR

logger = logging.getLogger(__name__)


class GemmaAnalyzer:
    """Gemma Vision Intelligence — calls the model for each analysis subtask.

    Each method loads a specific prompt and sends the cropped question image.
    """

    def __init__(self, llm):
        self.llm = llm
        self._prompts = {}

    def _load_prompt(self, name: str) -> str:
        if name not in self._prompts:
            path = Path(PROMPTS_DIR) / f"{name}.txt"
            if path.exists():
                self._prompts[name] = path.read_text(encoding="utf-8")
            else:
                logger.warning("Prompt file not found: %s", path)
                self._prompts[name] = ""
        return self._prompts[name]

    # ── Core inference ─────────────────────────────────────

    def analyze(self, image: np.ndarray, system_prompt: str, user_msg: str = "") -> dict:
        """Send an image + prompt to Gemma and parse JSON response."""
        _, buffer = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        b64 = base64.b64encode(buffer).decode("utf-8")

        resp = self.llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": system_prompt + "\n\n" + user_msg},
                ],
            }],
            max_tokens=GEMMA_MAX_TOKENS,
            temperature=GEMMA_TEMPERATURE,
        )
        raw = resp["choices"][0]["message"]["content"]
        parsed = self._parse_json(raw)
        return {"raw": raw, "parsed": parsed}

    def analyze_crop(self, crop_path: str | Path, system_prompt: str) -> dict:
        """Load a cropped image from disk, analyze, return result."""
        img = cv2.imread(str(crop_path))
        if img is None:
            raise ValueError(f"Cannot read crop: {crop_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self.analyze(img, system_prompt)

    # ── FLN Pipeline Prompts ───────────────────────────────

    def analyze_worksheet(self, image: np.ndarray) -> dict:
        """Prompt 1 — Universal Worksheet Analyzer: full worksheet structure."""
        prompt = self._load_prompt("worksheet_analyzer")
        return self.analyze(image, prompt, "Analyze this FLN worksheet.")

    def analyze_question(self, image: np.ndarray) -> dict:
        """Prompt 2 — Educational Question Analyzer: single question analysis."""
        prompt = self._load_prompt("question_analyzer")
        return self.analyze(image, prompt, "Analyze this question.")

    def classify_difficulty(self, image: np.ndarray) -> dict:
        """Prompt 3 — Difficulty Classification."""
        prompt = self._load_prompt("difficulty_classifier")
        return self.analyze(image, prompt, "Classify difficulty.")

    def understand_illustration(self, image: np.ndarray) -> dict:
        """Prompt 4 — Illustration Understanding."""
        prompt = self._load_prompt("illustration_understanding")
        return self.analyze(image, prompt, "Describe this illustration.")

    def normalize_question(self, image: np.ndarray, question_data: dict) -> dict:
        """Prompt 5 — Educational Normalization: normalize across publishers."""
        prompt = self._load_prompt("educational_normalization")
        context = f"Question context: {json.dumps(question_data, indent=2)}"
        return self.analyze(image, prompt, context)

    def validate_json(self, question_data: dict) -> dict:
        """Prompt 6 — JSON Validator: validate and fill missing fields."""
        prompt = self._load_prompt("json_validator")
        context = f"Question JSON: {json.dumps(question_data, indent=2)}"
        resp = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt + "\n\n" + context}],
            max_tokens=GEMMA_MAX_TOKENS,
            temperature=GEMMA_TEMPERATURE,
        )
        raw = resp["choices"][0]["message"]["content"]
        parsed = self._parse_json(raw)
        return {"raw": raw, "parsed": parsed}

    # ── JSON parsing ───────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r"```json\s*|```\s*", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            a, b = cleaned.find("{"), cleaned.rfind("}")
            if a != -1 and b > a:
                try:
                    return json.loads(cleaned[a:b+1])
                except json.JSONDecodeError:
                    pass
        return None

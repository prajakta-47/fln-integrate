import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Paths ──────────────────────────────────────────────────
RAW_DIR = BASE_DIR / "dataset" / "raw"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
CROPPED_DIR = BASE_DIR / "outputs" / "cropped_questions"
JSON_DIR = BASE_DIR / "outputs" / "json"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"
LOGS_DIR = BASE_DIR / "logs"
PROMPTS_DIR = BASE_DIR / "prompts"

for d in [RAW_DIR, PROCESSED_DIR, CROPPED_DIR, JSON_DIR, REPORTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Gemma Model ────────────────────────────────────────────
GEMMA_REPO_ID = "unsloth/gemma-4-26B-A4B-it-GGUF"
GEMMA_FILENAME = "gemma-4-26B-A4B-it-UD-Q5_K_XL.gguf"
GEMMA_MMPROJ = "mmproj-F16.gguf"
GEMMA_CACHE_DIR = "/root/gguf_cache"
GEMMA_N_CTX = 8192
GEMMA_N_GPU_LAYERS = -1
GEMMA_TEMPERATURE = 0.1
GEMMA_MAX_TOKENS = 8192

# ── Layout Detection ──────────────────────────────────────
LAYOUT_MODEL = "doclayout-yolo"  # or "yolov11"
LAYOUT_CONFIDENCE = 0.3
LAYOUT_MODEL_PATH = BASE_DIR / "models" / "yolo"

# ── Image Preprocessing ───────────────────────────────────
PREPROCESS_TARGET_SIZE = 1200
PREPROCESS_DESKEW_THRESHOLD = 3.0
PREPROCESS_BLUR_THRESHOLD = 80
PREPROCESS_CONTRAST_THRESHOLD = 100
PREPROCESS_CLAHE_CLIP = 2.0
PREPROCESS_CLAHE_TILE = 8

# ── Confidence Thresholds ─────────────────────────────────
CONFIDENCE_AUTO_SAVE = 0.90
CONFIDENCE_REVIEW = 0.70

# ── Supported Formats ─────────────────────────────────────
SUPPORTED_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
SUPPORTED_DOC_EXTS = {".pdf"}

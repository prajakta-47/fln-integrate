# Sidewise FLN Question Processor (Kaggle)

Processes worksheet question images (both **pre-cropped individual questions** and **full multi-question worksheet pages**) into a standardized Question Knowledge Base using **Gemma 4 26B A4B** (Mixture-of-Experts) on **2x T4 GPUs**.

**🔧 Auto-segmentation:** Full worksheet pages containing multiple questions are automatically detected and split into individual question crops before analysis.

## Overview

| Component | Description |
|-----------|-------------|
| **Model** | `unsloth/gemma-4-26B-A4B-it-GGUF` (MoE, ~4B active params/token) |
| **Quant** | `UD-Q4_K_XL` (17 GB) |
| **GPU** | 2x Tesla T4 (32 GB VRAM total) |
| **Library** | llama-cpp-python with CUDA |
| **Runtime** | Kaggle (GPU T4 x2 accelerator) |

## What This Pipeline Does

| Capability | Status |
|---|---|
| Analyze individual pre-cropped question images | ✅ |
| Extract educational concept, type, learning outcome | ✅ |
| Classify difficulty with numeric score + Easy/Medium/Hard calibration | ✅ |
| Describe illustrations (objects, counts, arrangement) | ✅ |
| Parse Gemma JSON output with fallback for malformed responses | ✅ |
| Retry failed images once, copy to manual review folder | ✅ |
| Aggregate results into a single knowledge_base.json | ✅ |
| **Auto-segment full worksheet pages into individual question crops** | ✅ |

## Setup

1. **Kaggle Settings** → Accelerator → **GPU T4 x2**
2. **Add-ons** → Secrets → Add `HF_TOKEN` (Hugging Face read token)
3. Upload zip files via **Add Data** button
4. **Cell → Run All**

## Input Format

Upload zips named `{level}.{sub_level}.zip`. Kaggle auto-extracts them into `/kaggle/input/{level}.{sub_level}/`.

```
1.0.zip  →  /kaggle/input/1.0/  →  Level 1, Sub-level 1.0
2.1.zip  →  /kaggle/input/2.1/  →  Level 2, Sub-level 2.1
```

Each zip may contain either **individual pre-cropped question images** or **full worksheet pages** with multiple questions. The pipeline automatically detects full pages via contour analysis and splits them into individual question crops before analysis. Each split crop is processed independently and given a `_crop{N}` suffix in its `question_id`, with the `bounding_box` field recording its position within the original page.

## Output

```
/kaggle/working/FLN_Knowledge_Base/
  ├── questions/          # Individual question JSON files
  │   ├── 1.0_001.json
  │   ├── 1.0_002.json
  │   └── ...
  ├── retry/              # Images that failed processing (manual review)
  └── knowledge_base.json # Aggregated knowledge base
```

Each question record follows a standardized schema:

```json
{
  "question_id": "1.0_001",
  "level": "1",
  "sub_level": "1.0",
  "worksheet_id": "1.0",
  "publisher": "IITRPR",
  "concept": "Counting",
  "learning_outcome": "Count objects up to 10",
  "question_type": "Counting",
  "instruction": "",
  "question_text": "",
  "illustration": {
    "objects": [],
    "count": 0,
    "arrangement": "",
    "purpose": ""
  },
  "difficulty": {
    "score": 50,
    "visual_complexity": 3,
    "reasoning_complexity": 3,
    "instruction_complexity": 3,
    "motor_skill": 3,
    "working_memory": 3,
    "relative_sublevel": "Medium"
  },
  "expected_answer": "",
  "cognitive_skills": [],
  "motor_skills": [],
  "template": "",
  "variables": {},
  "question_family": "",
  "bounding_box": {"x": 0, "y": 0, "width": 0, "height": 0},
  "confidence": 0.0
}
```

Key differences from the original schema:
- `difficulty` is now a **dict** with `score` (0-100), component ratings (1-5), and a calibrated `relative_sublevel` (Easy/Medium/Hard)
- `cognitive_skills` and `motor_skills` replace the old `skills` array
- `template`, `variables`, and `question_family` enable question reuse and random generation

### Difficulty Calibration

Within each sub-level, questions are ranked by their `difficulty.score` using percentile thresholds:
- **Easy**: score ≤ 30th percentile
- **Medium**: 30th < score ≤ 70th percentile
- **Hard**: score > 70th percentile

If fewer than 3 valid scores exist, all questions default to **Medium**.

## Pipeline Steps

| Cell | Step |
|------|------|
| 0 | Clean workspace + check disk |
| 1 | GPU check via `nvidia-smi` + install opencv (no PyTorch dependency) |
| 2 | Hugging Face login (HF_TOKEN) |
| 3 | Install llama-cpp-python (CUDA) + download & load Gemma 4 26B |
| 4 | Preprocessing engine (deskew, denoise, CLAHE) |
| 5 | **Question segmentation** (auto-split full pages) + Gemma 4 analysis prompt + JSON parsing |
| 6 | Concept normalization, record validation, repository logic |
| 7 | Batch processor — iterates input folders, runs analysis, calibrates difficulty, exports knowledge base |

### Cell Details

**Cell 1** — GPU check uses `nvidia-smi` instead of `import torch` to avoid a known Kaggle PyTorch circular import bug (`torch.fx` initialization) on Python 3.12.

**Cell 3** — CUDA version is detected via `nvidia-smi --query-gpu=cuda_version` for llama-cpp-python wheel selection. No PyTorch import needed.

**Cell 4** — Conditional preprocessing: deskew (>3°), bilateral denoising, unsharp masking (if blurry), CLAHE (if low contrast/blurry), upscaling (if <1200px min dimension). Dead store removed.

**Cell 6** — `validate_record()` ensures every field has valid defaults including a fallback difficulty dict with `"score": 50` when Gemma returns empty data.

**Cell 5** — `split_worksheet_questions()` segments full worksheet pages using adaptive thresholding + contour detection. It identifies content regions, merges spatially close regions, and performs column-aware splitting for multi-column layouts. If the analysis suggests a single question (e.g., dominant region >50% of image area), the original image is passed through unmodified. `process_image_or_page()` in Cell 7 calls this before analysis.

**Cell 7** — `process_image_or_page()` replaces the old `process_single_image()`. It calls `split_worksheet_questions()` first, then analyzes each crop independently. Split crops get `_crop{N}` question_id suffixes. Failed images are retried once, then copied to `retry/` for manual review.

## Analysis Performed

Each question image goes through a single **Gemma 4 26B call** with a comprehensive prompt that extracts:

1. **Educational Concept** — Counting, Matching, Tracing, Pattern Recognition, etc.
2. **Question Type** — Count Objects, Circle Correct, Match, Draw Line, etc.
3. **Learning Outcome** — The educational objective
4. **Cognitive Skills** — Observation, Reasoning, Memory, etc.
5. **Motor Skills** — Tracing, Coloring, Writing, etc.
6. **Question Text & Instruction** — Extracted text content
7. **Illustration Understanding** — Objects, counts, arrangement, purpose
8. **Variables & Template** — Reusable question parameters
9. **Expected Answer** — The correct response
10. **Difficulty Score** — 0-100 with component ratings
11. **Confidence** — Model's confidence in its analysis

## Bug Fixes & Improvements

The following issues were identified and fixed during code review:

| Issue | Location | Fix |
|---|---|---|
| PyTorch circular import (`torch.fx`) | Cell 1 | Replaced `import torch` with `nvidia-smi` GPU check |
| `IndentationError` from leading spaces | Cell 3 | Dedented GPU count lines to column 0 |
| Dead store `thresholded` not used | Cell 4 | Removed unused `cv2.adaptiveThreshold` call |
| `normalize_difficulty()` never called | Cell 6 | Removed dead function |
| `CONFIDENCE_REVIEW` never used | Cell 6 | Removed unused constant |
| Defaults dict had `score: 0` inconsistent with `score: 50` fallback | Cell 6 | Aligned all defaults to `score: 50` |
| Empty `{}` difficulty dict when Gemma fails to parse | Cell 6 & 7 | Added `if not isinstance(d, dict) or "score" not in d` checks in `validate_record()` and `process_single_image()` |
| 56/86 questions had `"unset"` relative_sublevel | Cell 7 | Added `if not scores:` early return in `calibrate_sublevel()` to handle empty score lists |
| `process_single_image` redefined per folder iteration | Cell 7 | Moved function definition outside the `for folder_name` loop |
| Redundant `total_questions` variable | Cell 7 | Replaced with `len(all_results)` |
| No full-page worksheet support | Cell 5 & 7 | Added `split_worksheet_questions()` (contour-based page segmentation) and `process_image_or_page()` that splts multi-question pages before analysis |

## First Run

- Downloads ~17 GB model GGUF + ~1.2 GB mmproj (cached in `/root/gguf_cache/`)
- Builds llama-cpp-python with CUDA support (~2 min)
- Model loads in ~2-3 min on 2x T4

## Notes

- The 26B A4B is a Mixture-of-Experts model — only ~4B params are active per token, enabling fast inference despite the 26B total size
- llama-cpp-python auto-splits layers across both T4 GPUs via `n_gpu_layers=-1`
- Flash attention is enabled (`flash_attn=True`)
- Context window: 8192 tokens (limited from model max 262144 for memory efficiency)
- Temperature: 0.1 (low randomness for consistent structured output)

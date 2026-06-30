#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLN Worksheet Question Extractor - extracts individual questions from a worksheet
image and produces clean JSON with question text and answers only.

Usage:
    python question_extractor.py --input /path/to/worksheet.jpg --output ./results

    from question_extractor import WorksheetExtractor
    extractor = WorksheetExtractor()
    results = extractor.process_image("worksheet.jpg")
"""

import os, sys, json, cv2, numpy as np, base64, re, time, argparse
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# SECTION 1: IMAGE PREPROCESSING
# ─────────────────────────────────────────────────────────────

def preprocess_image(img: np.ndarray) -> tuple:
    """Enhance image quality: deskew, sharpen, CLAHE, upscale if needed."""
    h, w = img.shape[:2]
    orig_h, orig_w = h, w
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    result = img.copy()
    applied = []

    is_blurry = bool(lap_var < 80)
    is_small = bool(min(h, w) < 800)
    is_low_contrast = bool((float(gray.max()) - float(gray.min())) < 100)

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    angle = 0.0
    if lines is not None:
        angles = []
        for line in lines:
            theta = line[0][1]
            deg = np.degrees(theta) - 90
            if abs(deg) < 30:
                angles.append(deg)
        if angles:
            angle = float(np.median(angles))
    is_skewed = bool(abs(angle) > 3.0)

    if is_skewed:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        result = cv2.warpAffine(result, M, (w, h),
                                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        applied.append(f"deskew {angle:.1f} deg")
        h, w = result.shape[:2]

    if is_blurry:
        blurred = cv2.GaussianBlur(result, (0, 0), 3.0)
        sharp = cv2.addWeighted(result, 1.5, blurred, -0.5, 0)
        sharp = np.clip(sharp, 0, 255).astype(np.uint8)
        new_var = cv2.Laplacian(cv2.cvtColor(sharp, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
        if new_var > lap_var:
            result = sharp
            applied.append("unsharp")

    if is_low_contrast or is_blurry:
        lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        result = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        applied.append("CLAHE")

    if is_small:
        scale = max(1.0, 800 / min(h, w))
        if scale > 1.1:
            result = cv2.resize(result, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_CUBIC)
            applied.append(f"upscale {scale:.1f}x")

    info = {
        "blurry": is_blurry, "skewed": is_skewed, "small": is_small,
        "low_contrast": is_low_contrast, "lap_var": round(float(lap_var), 1),
        "angle": round(float(angle), 1), "original_size": f"{orig_w}x{orig_h}",
        "applied": applied
    }
    return result, info


# ─────────────────────────────────────────────────────────────
# SECTION 2: QUESTION SEGMENTATION
# ─────────────────────────────────────────────────────────────

def segment_questions(img: np.ndarray) -> list:
    """Detect individual question regions using projection profile analysis.
    Falls back to contour detection if projection returns zero questions.
    Returns list of {bbox, crop, idx} sorted top-to-bottom, left-to-right."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 5))
    dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    row_proj = np.sum(dilated, axis=1) // 255
    threshold = w * 0.02
    content_rows = row_proj > threshold

    row_bands = []
    in_band = False
    start = 0
    for i in range(len(content_rows)):
        if content_rows[i] and not in_band:
            start = i
            in_band = True
        elif not content_rows[i] and in_band:
            if i - start > 50:
                row_bands.append((start, i))
            in_band = False
    if in_band and len(content_rows) - start > 50:
        row_bands.append((start, len(content_rows)))

    questions = []
    q_idx = 0

    for ry1, ry2 in row_bands:
        row_img = binary[ry1:ry2, :]
        row_h, row_w = row_img.shape

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, int(row_h * 0.3)))
        row_dilated = cv2.morphologyEx(row_img, cv2.MORPH_CLOSE, v_kernel)

        col_proj = np.sum(row_dilated, axis=0) // 255
        col_threshold = row_h * 0.05

        col_bands = []
        in_band = False
        start = 0
        for j in range(len(col_proj)):
            if col_proj[j] > col_threshold and not in_band:
                start = j
                in_band = True
            elif col_proj[j] <= col_threshold and in_band:
                if j - start > 30:
                    col_bands.append((start, j))
                in_band = False
        if in_band and len(col_proj) - start > 30:
            col_bands.append((start, len(col_proj)))

        if not col_bands:
            col_bands = [(0, row_w)]
        elif len(col_bands) > 1:
            min_col_w = w * 0.25
            narrow_cols = [b for b in col_bands if (b[1] - b[0]) < min_col_w]
            narrow_total = sum(b[1]-b[0] for b in narrow_cols)
            if narrow_total < w * 0.10 or (len(narrow_cols) == len(col_bands) and narrow_total < w * 0.30):
                col_bands = [(0, row_w)]

        for cx1, cx2 in col_bands:
            x1 = max(0, cx1 - 5)
            x2 = min(w, cx2 + 5)
            y1 = max(0, ry1 - 5)
            y2 = min(h, ry2 + 5)

            crop = img[y1:y2, x1:x2]
            if crop.shape[0] < 30 or crop.shape[1] < 30:
                continue

            q_idx += 1
            questions.append({
                "idx": q_idx,
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
                "crop": crop,
            })

    if not questions:
        print("  Projection found 0 questions, trying contour fallback...")
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = h * w * 0.005
        regions = []
        for cnt in contours:
            x, y, rw, rh = cv2.boundingRect(cnt)
            if rh > 30 and rw > 50 and rh * rw > min_area:
                regions.append((y, x, rw, rh))
        regions.sort(key=lambda r: (r[0], r[1]))
        for y, x, rw, rh in regions:
            q_idx += 1
            y1 = max(0, y - 5)
            y2 = min(h, y + rh + 5)
            x1 = max(0, x - 5)
            x2 = min(w, x + rw + 5)
            crop = img[y1:y2, x1:x2]
            questions.append({
                "idx": q_idx,
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
                "crop": crop,
            })
        print(f"  Contour fallback found {len(questions)} region(s)")

    return questions


# ─────────────────────────────────────────────────────────────
# SECTION 3: GEMMA ANALYSIS PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_BASE = """You are an expert FLN (Foundational Literacy and Numeracy) worksheet analyst.
Look at this SINGLE QUESTION CROP from a children's worksheet (Grades 1-3).

Extract ONLY:
1. question_text - The exact instruction/question text as it appears in the image (transcribed verbatim)
2. answer - The correct answer (be precise: number, word, letter, or short phrase)

RULES for ALL FLN question types:

NUMERACY:
- Counting / "How many?" / "Count and write" -> write only the number
- "Circle the number" / "Identify the number" -> write the number itself
- "Write the number" / "Trace the number" -> write the number
- "Before / After / Between" -> write the missing number (e.g. "__ , 5, 6" -> "4")
- "Greater than / Less than / Bigger / Smaller" -> write the correct number or symbol
- "Ascending / Descending order" -> write the sequence separated by ";"
- Addition / Subtraction / "Add" / "Subtract" / "Find the sum/difference" -> write only the numeric answer
- "Missing number" / "Number pattern" -> write the missing value(s) separated by ";"
- "Number line" -> write the number to be circled/marked/identified
- "Tens and Ones" / "Place value" -> write the value (e.g. "3 tens 5 ones = 35")
- "More / Less" / "Many / Few" -> write the number or group name
- "Same / Different" -> write which one is same/different
- "Match the following" / "Join the following" / "Match by counting" -> write as "A->X;B->Y"
- "Colour the number" / "Colour the correct answer" -> write the color word itself (e.g. "red")
- "Circle / Tick / Underline / Choose the correct answer" -> write the option text itself
- "True or False" / "Yes or No" -> write "true"/"false" or "yes"/"no"

LITERACY:
- Fill in the blank -> write the missing word(s) only
- "Write the first letter" / "Match the letter" -> write the letter
- "Unscramble" / "Arrange" -> write the correct word
- "Rhyming words" / "Same sound" -> write the rhyming word
- "Vowels / Consonants" -> write the vowel/consonant
- "Opposites" -> write the opposite word
- "One / Many" (singular/plural) -> write the correct form

GENERAL:
- "Draw" / "Make" / "Show" instructions -> briefly describe what should be drawn
- "Maze / Path tracing" -> write the starting/ending point
- "Pattern completion" (shapes/colors/numbers) -> write the next item(s) separated by ";"
- "Sort / Classify / Group" -> write the category and items separated by ";"
- "Odd one out" -> write the item that is different
- Clock / Time -> write the time shown (e.g. "3 o'clock" or "3:00")
- Money / Coins -> write the total value
- Measurement (long/short, heavy/light, tall/short, full/empty) -> write the answer as shown
- "Cross the odd one" / "Tick the correct" -> write the selected item
- Skip counting / "Count by 2s/5s/10s" -> write the sequence separated by ";"
- Word problems / "Story sums" -> write only the numeric answer
- Expanded form / Short form -> write the expanded or short form (e.g. "30 + 5" or "35")
- Calendar / Days of the week / Months -> write the day/month name
- Fractions (half/quarter/full) -> write the fraction (e.g. "1/2" or "half")
- Data handling / Pictograph / "Count the tally marks" -> write the count
- "Put the correct sign" (>, <, =) -> write the symbol
- Articles (a/an/the) -> write the correct article
- Gender (masculine/feminine) -> write "masculine" or "feminine"
- Naming words / Action words / Describing words -> write the word as categorized
- Punctuation (. , ? !) -> write the correct punctuation mark
- One/many (singular/plural) -> write the plural form

{
  "question_text": "",
  "answer": ""
}
"""

RETRY_HINTS = [
    "",
    "IMPORTANT: Both question_text and answer must be non-empty. Double-check the image carefully.",
    "CRITICAL: You MUST provide BOTH question_text (verbatim transcript) AND answer. Do NOT leave any field empty or null. If unsure, make your best guess.",
]


def _extract_json(text: str) -> tuple:
    """Robust JSON extraction from model output. Returns (parsed_dict, error_str)."""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    cleaned = re.sub(r'```json\s*|```\s*', '', cleaned).strip()

    cleaned = re.sub(r'^[^{]*', '', cleaned)
    cleaned = re.sub(r'[^}]*$', '', cleaned)
    if not cleaned:
        return None, "no JSON object found"

    # Try to parse complete JSON
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Strip trailing comma before } or ]
    cleaned_tc = re.sub(r',\s*}', '}', cleaned)
    cleaned_tc = re.sub(r',\s*]', ']', cleaned_tc)
    try:
        return json.loads(cleaned_tc), None
    except json.JSONDecodeError:
        pass

    # Strip bad escape sequences
    cleaned_esc = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', '', cleaned)
    try:
        return json.loads(cleaned_esc), None
    except json.JSONDecodeError:
        pass

    # Handle multiple JSON objects like {"thinking":"..."}{"question_text":"...","answer":"..."}
    if '}{' in cleaned:
        parts = cleaned.split('}{')
        for i in range(len(parts)):
            candidate = parts[i]
            if i > 0:
                candidate = '{' + candidate
            if i < len(parts) - 1:
                candidate = candidate + '}'
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and ("question_text" in parsed or "answer" in parsed):
                    return parsed, None
            except json.JSONDecodeError:
                continue

    return None, "could not parse JSON after all fallbacks"


def analyze_question(llm, img: np.ndarray, name: str, max_retries: int = 3) -> dict:
    """Send a single question crop to Gemma and parse JSON response.
    Retries up to `max_retries` times if validation fails.
    """
    if llm is None:
        return {"file": name, "raw": "", "parsed": None, "error": "llm is None (model not loaded)", "attempts": 0}

    _, buffer = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    b64 = base64.b64encode(buffer).decode("utf-8")

    best = {"file": name, "raw": "", "parsed": None, "error": "max retries exceeded", "attempts": 0}

    for attempt in range(1, max_retries + 1):
        hint = RETRY_HINTS[min(attempt - 1, len(RETRY_HINTS) - 1)]
        user_text = SYSTEM_PROMPT_BASE
        if hint:
            user_text += "\n\n" + hint
        user_text += "\n\nAnalyze this single FLN question image."

        resp = llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": user_text},
                ],
            }],
            max_tokens=1024, temperature=0.1 + (attempt - 1) * 0.1,
        )

        raw = resp["choices"][0]["message"]["content"]
        parsed, error = _extract_json(raw)

        if parsed and isinstance(parsed, dict):
            qt = str(parsed.get("question_text", "")).strip()
            an = str(parsed.get("answer", "")).strip()

            if qt and an:
                best = {"file": name, "raw": raw, "parsed": parsed, "error": None, "attempts": attempt}
                break

            if qt and not an:
                best = {"file": name, "raw": raw, "parsed": parsed, "error": "empty answer", "attempts": attempt}
            elif an and not qt:
                best = {"file": name, "raw": raw, "parsed": parsed, "error": "empty question_text", "attempts": attempt}
            else:
                best = {"file": name, "raw": raw, "parsed": parsed, "error": "both fields empty", "attempts": attempt}
        else:
            best = {"file": name, "raw": raw, "parsed": None, "error": error or "unknown", "attempts": attempt}

    if best["parsed"] and isinstance(best["parsed"], dict):
        best["parsed"].setdefault("question_text", "")
        best["parsed"].setdefault("answer", "")

    return best


# ─────────────────────────────────────────────────────────────
# SECTION 4: NUMPY JSON ENCODER
# ─────────────────────────────────────────────────────────────

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# ─────────────────────────────────────────────────────────────
# SECTION 5: MAIN EXTRACTOR CLASS
# ─────────────────────────────────────────────────────────────

class WorksheetExtractor:
    """Extract questions from a worksheet image and analyze each with Gemma."""

    def __init__(self, llm=None):
        self.llm = llm

    def load_gemma(self, model_path: str = None, cache_dir: str = "/root/gguf_cache"):
        """Load Gemma 4 26B A4B model. Call this on Kaggle/Colab."""
        if self.llm is not None:
            return

        from llama_cpp import Llama, llama_supports_gpu_offload
        from llama_cpp.llama_chat_format import Gemma4ChatHandler
        import torch

        os.makedirs(cache_dir, exist_ok=True)

        # Detect GPU
        gpu_avail = torch.cuda.is_available()
        gpu_count = torch.cuda.device_count() if gpu_avail else 0

        if gpu_avail:
            for i in range(gpu_count):
                total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                print(f"  GPU {i}: {torch.cuda.get_device_name(i)} ({total:.0f} GB)")

        # Check if llama-cpp-python was built with CUDA support
        has_gpu = gpu_avail and llama_supports_gpu_offload()
        if gpu_avail and not has_gpu:
            print("  WARNING: GPUs detected but llama-cpp-python was NOT built with CUDA support.")
            print("  Install with: CMAKE_ARGS='-DLLAMA_CUDA=on' pip install llama-cpp-python --force-reinstall")
            print("  Falling back to CPU (very slow for large models).")
        else:
            print(f"  llama-cpp GPU offload: {'YES' if has_gpu else 'NO'}")

        print("Loading Gemma 4 26B chat handler...")
        CHAT_HANDLER = Gemma4ChatHandler.from_pretrained(
            repo_id="unsloth/gemma-4-26B-A4B-it-GGUF",
            filename="mmproj-F16.gguf",
            local_dir=cache_dir, verbose=False,
        )

        # Select model based on VRAM
        if gpu_avail:
            total_vram = sum(torch.cuda.get_device_properties(i).total_memory for i in range(gpu_count))
            model_file = "gemma-4-26B-A4B-it-UD-Q5_K_XL.gguf" if total_vram >= 22 * (1024**3) else "gemma-4-26B-A4B-it-Q4_K_M.gguf"
            print(f"Total VRAM: {total_vram/(1024**3):.0f} GB -> {model_file}")
        else:
            model_file = "gemma-4-26B-A4B-it-Q4_K_M.gguf"
            print(f"No GPU detected -> {model_file} (CPU)")

        print(f"Loading {model_file}... (this takes ~15 min on first run)")

        model_kwargs = dict(
            repo_id="unsloth/gemma-4-26B-A4B-it-GGUF",
            filename=model_file,
            local_dir=cache_dir,
            chat_handler=CHAT_HANDLER,
            n_ctx=8192,
            verbose=True,
        )

        if has_gpu:
            model_kwargs["n_gpu_layers"] = -1
            model_kwargs["flash_attn"] = True
            model_kwargs["main_gpu"] = 0
            if gpu_count > 1:
                props = [torch.cuda.get_device_properties(i) for i in range(gpu_count)]
                total_mem = sum(p.total_memory for p in props)
                model_kwargs["tensor_split"] = [p.total_memory / total_mem for p in props]
                print(f"Tensor split: {[round(s, 3) for s in model_kwargs['tensor_split']]}")
        else:
            model_kwargs["n_gpu_layers"] = 0

        start = time.time()
        self.llm = Llama.from_pretrained(**model_kwargs)
        elapsed = (time.time() - start) / 60
        print(f"Model loaded in {elapsed:.1f} min")
        if has_gpu:
            print(f"GPU layers: {self.llm.llama.n_gpu_layers()}")

    def process_image(self, image_path: str, output_dir: str = None, save_crops: bool = True) -> dict:
        """Process a single worksheet image: segment -> analyze each question -> return results."""
        name = Path(image_path).name
        stem = Path(image_path).stem

        if output_dir:
            ws_dir = Path(output_dir) / stem
            ws_dir.mkdir(parents=True, exist_ok=True)
            crops_dir = ws_dir / "crops"
            if save_crops:
                crops_dir.mkdir(exist_ok=True)

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Cannot read image: {image_path}")
        img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        print(f"  Input: {img.shape[1]}x{img.shape[0]}")

        processed_img, info = preprocess_image(img)
        if info["applied"]:
            print(f"  Preprocessing: {', '.join(info['applied'])}")
        else:
            print("  Preprocessing: none needed")

        if output_dir:
            enhanced_path = ws_dir / name
            cv2.imwrite(str(enhanced_path), cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))

        questions = segment_questions(processed_img)
        print(f"  Questions detected: {len(questions)}")

        worksheet_data = {"worksheet": name, "questions": []}

        for q in questions:
            q_idx = q["idx"]
            crop_name = f"{stem}_q{q_idx}.png"
            print(f"  [{q_idx}/{len(questions)}] Analyzing...")

            if output_dir and save_crops:
                try:
                    crop_path = crops_dir / crop_name
                    cv2.imwrite(str(crop_path), cv2.cvtColor(q["crop"], cv2.COLOR_RGB2BGR))
                except Exception as e:
                    print(f"    WARN: could not save crop {crop_name}: {e}")

            try:
                result = analyze_question(self.llm, q["crop"], crop_name)
            except Exception as e:
                result = {"file": crop_name, "raw": "", "parsed": None, "error": str(e), "attempts": 0}

            q_text = ""
            q_answer = ""
            if result["parsed"]:
                q_text = result["parsed"].get("question_text", "")
                q_answer = result["parsed"].get("answer", "")
            elif result["error"]:
                q_text = f"[PARSE ERROR: {result['error']}]"

            entry = {
                "question_number": q_idx,
                "question_text": q_text,
                "answer": q_answer,
            }
            worksheet_data["questions"].append(entry)
            print(f"    Q{q_idx}: {q_text[:60] if q_text else '[empty]'} -> {q_answer[:40] if q_answer else '[empty]'}")

        if output_dir:
            out_path = ws_dir / f"{stem}_qa.json"
            with open(out_path, "w") as f:
                json.dump(worksheet_data, f, indent=2)
            print(f"  Saved: {out_path}")

        return worksheet_data

    def process_batch(self, input_paths: list, output_dir: str = None) -> list:
        """Process multiple worksheet images."""
        all_results = []
        for i, path in enumerate(input_paths, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(input_paths)}] {Path(path).name}")
            print(f"{'='*60}")
            result = self.process_image(path, output_dir=output_dir)
            all_results.append(result)
        return all_results

    def generate_report(self, all_results: list) -> dict:
        """Generate a combined Q&A report from all worksheets."""
        return {"worksheets": all_results}


# ─────────────────────────────────────────────────────────────
# SECTION 6: CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FLN Worksheet Question Extractor - split worksheets into questions and extract answers"
    )
    parser.add_argument("--input", "-i", required=True, nargs="+",
                        help="Input worksheet image(s) or directory")
    parser.add_argument("--output", "-o", default="./FLN_Results",
                        help="Output directory for results (default: ./FLN_Results)")
    parser.add_argument("--no-crops", action="store_true",
                        help="Don't save individual question crop images")

    args = parser.parse_args()

    input_paths = []
    for p in args.input:
        path = Path(p)
        if path.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tiff"):
                input_paths.extend(sorted(path.rglob(ext)))
        elif path.is_file():
            input_paths.append(path)

    if not input_paths:
        print("No images found.")
        sys.exit(1)

    print(f"Found {len(input_paths)} image(s)")
    print("Loading Gemma 4 26B... (first run downloads ~17 GB model)")

    extractor = WorksheetExtractor()
    extractor.load_gemma()

    results = extractor.process_batch(
        [str(p) for p in input_paths],
        output_dir=args.output,
        save_crops=not args.no_crops,
    )

    report = extractor.generate_report(results)

    report_path = Path(args.output) / "all_questions_answers.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    total_qs = sum(len(r["questions"]) for r in results)
    print(f"\n{'='*60}")
    print(f"COMPLETE: {len(results)} worksheet(s), {total_qs} questions")
    print(f"Combined Q&A: {report_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

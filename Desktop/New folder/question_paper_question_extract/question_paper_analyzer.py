#!/usr/bin/env python3
"""
Question Paper Analyzer v2
Extracts every question from a worksheet image and produces a detailed JSON
describing EVERYTHING visible inside each question — text, objects, answer
spaces, structure — without including the answer.

Usage:
    python question_paper_analyzer.py -i worksheet.jpg -o ./results
    python question_paper_analyzer.py -i workspace_results/ -o ./results
    python question_paper_analyzer.py -i image.png -o ./results --no-model
"""
import os, sys, json, cv2, numpy as np, base64, re, time, argparse, csv
from pathlib import Path
from io import StringIO

# --- Named constants for segmentation ---
SEG_ROW_KERNEL_DIV = 80
SEG_ROW_KERNEL_WIDTH_DIV = 4
SEG_ROW_PROJ_THRESH = 0.015
SEG_MIN_ROW_H_DIV = 60
SEG_V_KERNEL_W_DIV = 60
SEG_V_KERNEL_H_RATIO = 0.25
SEG_COL_THRESH_RATIO = 0.05
SEG_MIN_COL_W_DIV = 40
SEG_WIDE_COL_MIN_RATIO = 0.2
SEG_VALID_COL_RATIO = 0.15
SEG_CROP_PAD = 4
SEG_MIN_CROP_H = 25
SEG_MIN_CROP_W = 25
SEG_CONTOUR_MIN_AREA = 0.003
SEG_CONTOUR_MIN_H = 25
SEG_CONTOUR_MIN_W = 40
SEG_RESEGMENT_THRESH = 350
SEG_FRAGMENT_H = 50
SEG_FRAGMENT_H2 = 70
SEG_FRAGMENT_ASPECT = 5
SEG_FRAGMENT_GAP = 45
SEG_FILTER_HEADER_TOP = 0.08
SEG_FILTER_HEADER_H = 80
SEG_FILTER_HEADER_H2 = 120
SEG_FILTER_HEADER_ASPECT = 5
SEG_FILTER_FOOTER_BOT = 0.88
SEG_FILTER_FOOTER_H = 60
SEG_FILTER_BOTTOM_STRIP_BOT = 0.95
SEG_FILTER_BOTTOM_STRIP_H = 100
SEG_FILTER_SMALL_AREA = 0.005
SEG_FILTER_SMALL_H = 40
SEG_FILTER_SMALL_W = 80
SEG_FILTER_NOISE_H = 30
SEG_FILTER_NOISE_W = 30
SEG_HEADER_GUARD_RATIO = 0.065  # fraction of img_h: trim header from first band if it merged
SEG_HEADER_GAP_MIN = 10  # min px gap to split header from Q1
SEG_INSTRUCTION_MIN_WIDTH_RATIO = 0.6  # min fraction of img_w for instruction line detection
SEG_RESEGMENT_FINER_THRESH_FACTOR = 1.15  # resegment finer pass if region h >= SEG_RESEGMENT_THRESH * this

# --- Question numbering patterns for group detection ---
# Regex patterns that identify a question number prefix (tried in order).
# The first capture group must extract the question number.
# Override Q_NUMBER_PATTERNS before calling process_image to adapt to different formats.
Q_NUMBER_PATTERNS = [
    r'^(\d+)\)\s*',          # "1) Match..."  (default)
    r'^(\d+)\.\s*',          # "1. Match..."
    r'^\((\d+)\)\s*',        # "(1) Match..."
    r'^Q\.?\s*(\d+)\s*',     # "Q.1 Match..." / "Q1 Match..."
    r'^Question\s+(\d+)\s*', # "Question 1 Match..."
    r'^(\d+)\s*[.\)]?\s*$', # Bare "1" or "1." (instruction may be in sub-text)
    r'^\(?([A-D])\)?\.?\s*',   # "A)" / "A." / "(A)" — multiple choice parts
    r'^\(?([ivxlcdm]+)\)\s*', # "(i)" / "(ii)" lowercase Roman
    r'^Step\s+(\d+)\s*',    # "Step 1", "Step 2"
]

# --- Layout detection constants ---
LAYOUT_SAMPLE_STEP = 4          # pixel stride for projection sampling
LAYOUT_COL_GAP_MIN_RATIO = 0.03  # min fraction of img_w that qualifies as a column gap
LAYOUT_COL_MIN_WIDTH_RATIO = 0.15 # min fraction of img_w for a valid column
LAYOUT_GRID_CELL_MIN_RATIO = 0.10 # min fraction of img_h for a grid cell
LAYOUT_FREEFORM_AREA_RATIO = 0.015 # min area ratio for freeform components

# --- Preprocessing constants ---
PREP_BLUR_THRESH = 80
PREP_SMALL_THRESH = 800
PREP_CONTRAST_THRESH = 100
PREP_SKEW_THRESH = 3.0
PREP_SHARPEN_WEIGHT = 1.5
PREP_SHARPEN_NEG = -0.5
PREP_UPSCALE_MIN = 1.1

# --- Analysis constants ---
ANALYSIS_MAX_TOKENS = 6144
ANALYSIS_MAX_RETRIES = 3
ANALYSIS_BASE_TEMP = 0.1
ANALYSIS_TEMP_STEP = 0.1
ANALYSIS_LARGE_CROP_WARN = 400  # pixels in shorter dimension


QUESTION_EXTRACT_PROMPT = """You are analyzing a SINGLE QUESTION crop from a children's worksheet.
Read the image CAREFULLY and extract every visible detail.

YOUR MOST IMPORTANT TASK: Read and transcribe ALL text EXACTLY as written — the main instruction, item numbers, labels, and any numbers inside illustrations. If the question has text, question_text MUST contain it VERBATIM.

Return ONLY valid JSON with this exact structure (no markdown, no thinking tags):
{
  "question_text": "EXACT instruction text verbatim. Read every word carefully. If purely pictorial set empty string.",
  "all_visible_text": [{"text": "every piece of text visible", "position": "top|middle|bottom|left|right|center|inside-object|beside-object|label"}],
  "instruction_verb": "Count|Match|Circle|Colour|Write|Trace|Tick|Draw|Join|Add|Subtract|Read|Identify|Fill|Solve|Find|Connect|Observe|Complete|Cross",
  "question_type": "Counting|Matching|Addition|Subtraction|Number-Recognition|Pattern|Odd-One-Out|Comparison|Place-Value|Shape-Recognition|Time|Money|Letter-Recognition|Word-Formation|Fill-Blank|Sequencing|Sorting|Colouring|Join-Dots|Tracing|Writing-Practice|Data-Handling",
  "question_sub_type": "Count-And-Write|Count-And-Circle|Count-And-Match|Match-Number-To-Word|Match-Column|Circle-Correct|Fill-Missing|Tens-Ones|Ascending|Descending|True-False|Greater-Less|Before-After-Between|Number-Bond|Story-Sum|Draw-Color|Complete-Pattern|Trace-Write|Unscramble|Rhyming",
  "structure": "single-item|multiple-items|matching-columns|grid|table|fill-in-series|with-illustration|text-only|horizontal-row|vertical-list",
  "item_count": 0,
  "items": [{"item_number": 1, "text": "item specific text/label", "objects": [], "answer_space": {}}],
  "objects": [{"name": "object name (singular, e.g. apple not apples)", "count": 5, "attributes": ["red", "small"], "position": "top-left|center|scattered|row|column", "arrangement": "row|grid|scattered|grouped"}],
  "total_object_count": 0,
  "illustration_purpose": "counting|identification|matching|comparison|story-context|visual-discrimination|pattern-recognition|number-recognition|coloring-practice",
  "answer_spaces": [{"type": "blank|box|circle|line|dotted-line|empty-cell|tick-box|match-line|bracket", "count": 1, "location": "below-text|beside-text|inside-text|at-end|in-illustration", "associated_item_number": 0}],
  "visual_elements": ["border|dotted-line|arrow|number-label|icon|table-grid|frame|star|underline|box-border|circle-border"],
  "colors_mentioned": ["red|blue|green|yellow|orange|purple|pink|brown|black|white"],
  "relational_words": ["more|less|bigger|smaller|same|different|before|after|between|greater|fewer|many|most|least"],
  "group_context": {"is_grouped": false, "group_id": 0, "group_instruction": ""},
  "concept": "FLN concept name",
  "learning_outcome": "measurable skill description",
  "cognitive_skill": "Remembering|Understanding|Applying|Analyzing",
  "motor_skill": "Writing|Circling|Matching|Colouring|Tracing|Drawing|Tick-Marking",
  "difficulty": "Easy|Medium|Hard"
}

RULES:
- question_text: Copy the main instruction WORD FOR WORD. This is critical.
- all_visible_text: Include EVERY number, letter, label, and word fragment visible — including item numbers like "1.", "2." and labels inside illustrations.
- objects: List each DISTINCT object type once with its count. Be precise about count.
- answer_spaces: List every blank, box, or writing line.
- Do NOT include the answer, expected_answer, or correct_answer.
- Use "" for empty text, [] for empty lists, {} for empty objects, 0 for zero, false for booleans."""


def preprocess_image(img: np.ndarray) -> tuple:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    is_blurry = lap_var < PREP_BLUR_THRESH
    is_small = min(h, w) < PREP_SMALL_THRESH
    is_low_contrast = (float(gray.max()) - float(gray.min())) < PREP_CONTRAST_THRESH

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
    is_skewed = abs(angle) > PREP_SKEW_THRESH

    needs_processing = is_skewed or is_blurry or is_low_contrast or is_small
    result = img.copy() if needs_processing else img
    applied = []

    if is_skewed:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        result = cv2.warpAffine(result, M, (w, h),
                                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        applied.append(f"deskew_{angle:.1f}deg")
        h, w = result.shape[:2]

    if is_blurry:
        blurred = cv2.GaussianBlur(result, (0, 0), 3.0)
        sharp = cv2.addWeighted(result, PREP_SHARPEN_WEIGHT, blurred, PREP_SHARPEN_NEG, 0)
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
        applied.append("clahe")

    if is_small:
        scale = max(1.0, PREP_SMALL_THRESH / min(h, w))
        if scale > PREP_UPSCALE_MIN:
            result = cv2.resize(result, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_CUBIC)
            applied.append(f"upscale_{scale:.1f}x")

    info = {
        "blurry": bool(is_blurry), "skewed": bool(is_skewed), "small": bool(is_small),
        "low_contrast": bool(is_low_contrast), "lap_var": round(float(lap_var), 1),
        "angle": round(float(angle), 1), "original_size": f"{img.shape[1]}x{img.shape[0]}",
        "applied": applied
    }
    return result, info


def _detect_column_gaps(binary: np.ndarray, h: int, w: int) -> list:
    n_slices = max(3, h // 300)
    slice_h = h // n_slices
    margin = max(1, w // 20)
    min_gap_w = max(int(w * LAYOUT_COL_GAP_MIN_RATIO), 1)
    gap_confidence = np.zeros(w)

    for si in range(n_slices):
        sy = si * slice_h
        ey = min(h, sy + slice_h)
        if ey - sy < 30:
            continue
        slice_binary = binary[sy:ey, :]
        col_proj = np.sum(slice_binary, axis=0) // 255
        col_max = col_proj.max()
        if col_max == 0:
            continue
        col_norm = col_proj / col_max
        in_gap = False
        start = 0
        for i in range(len(col_norm)):
            if i < margin or i > w - margin:
                if in_gap:
                    if i - start >= min_gap_w:
                        gap_confidence[start:i] += 1
                    in_gap = False
                continue
            if col_norm[i] < 0.05 and not in_gap:
                start = i
                in_gap = True
            elif col_norm[i] >= 0.05 and in_gap:
                if i - start >= min_gap_w:
                    gap_confidence[start:i] += 1
                in_gap = False
        if in_gap and len(col_norm) - start >= min_gap_w:
            gap_confidence[start:len(col_norm)] += 1

    min_confidence = max(1, n_slices * 0.5)
    col_gaps = []
    in_gap = False
    start = 0
    for i in range(w):
        if gap_confidence[i] >= min_confidence and not in_gap:
            start = i
            in_gap = True
        elif gap_confidence[i] < min_confidence and in_gap:
            if i - start >= min_gap_w:
                col_gaps.append((start, i))
            in_gap = False
    if in_gap and w - start >= min_gap_w:
        col_gaps.append((start, w))

    return [g for g in col_gaps if g[0] > margin and g[1] < w - margin]


def detect_layout_type(img: np.ndarray, binary: np.ndarray = None) -> str:
    h, w = img.shape[:2]
    if binary is None:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    inner_gaps = _detect_column_gaps(binary, h, w)
    min_gap_w = max(int(w * LAYOUT_COL_GAP_MIN_RATIO), 1)
    margin = max(1, w // 20)

    if len(inner_gaps) >= 1:
        n_cols = len(inner_gaps) + 1
        if n_cols >= 3:
            return "multi-column"
        gx1, gx2 = inner_gaps[0]
        strip_w = max(min_gap_w * 5, int(w * 0.05))
        left_content = np.mean(np.sum(binary[:, max(0, gx1 - strip_w):gx1], axis=1) // 255 > 0)
        right_content = np.mean(np.sum(binary[:, gx2:min(w, gx2 + strip_w)], axis=1) // 255 > 0)
        if left_content > 0.15 and right_content > 0.15:
            total_left = np.sum(binary[:, :gx1]) // 255
            total_right = np.sum(binary[:, gx2:]) // 255
            # Require right column to contain >= 25% of total content (excludes sparse sidebar)
            right_fraction = total_right / max(total_left + total_right, 1)
            if right_fraction < 0.25:
                return "single-column"
            # Balance check: content ratio <= 3:1
            content_ratio = max(total_left, total_right) / max(min(total_left, total_right), 1)
            if content_ratio >= 3.0:
                return "single-column"
            return "two-column"

    col_proj_full = np.sum(binary[::LAYOUT_SAMPLE_STEP, :], axis=0) // 255
    col_norm_full = col_proj_full / col_proj_full.max() if col_proj_full.max() > 0 else col_proj_full
    row_proj_full = np.sum(binary[:, ::LAYOUT_SAMPLE_STEP], axis=1) // 255
    row_norm_full = row_proj_full / row_proj_full.max() if row_proj_full.max() > 0 else row_proj_full

    col_fill = np.mean(col_norm_full[margin:-margin] > 0.03) if w > margin * 2 else np.mean(col_norm_full > 0.03)
    row_fill = np.mean(row_norm_full > 0.03)

    if col_fill > 0.4:
        return "single-column"
    if row_fill > 0.4:
        return "grid"
    return "freeform"


def segment_single_column(img: np.ndarray, binary: np.ndarray, h: int, w: int) -> list:
    row_kernel_h = max(5, h // SEG_ROW_KERNEL_DIV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // SEG_ROW_KERNEL_WIDTH_DIV, row_kernel_h))
    dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    row_proj = np.sum(dilated, axis=1) // 255
    threshold = w * SEG_ROW_PROJ_THRESH
    content_rows = row_proj > threshold

    row_bands = []
    in_band = False
    start = 0
    min_row_h = max(20, h // SEG_MIN_ROW_H_DIV)
    for i in range(len(content_rows)):
        if content_rows[i] and not in_band:
            start = i
            in_band = True
        elif not content_rows[i] and in_band:
            if i - start > min_row_h:
                row_bands.append((start, i))
            in_band = False
    if in_band and len(content_rows) - start > min_row_h:
        row_bands.append((start, len(content_rows)))

    # --- HEADER GUARD: if first band includes both header and Q1 content, split it ---
    header_guard_px = int(h * SEG_HEADER_GUARD_RATIO)
    if row_bands and row_bands[0][0] < header_guard_px and (row_bands[0][1] - row_bands[0][0]) > SEG_FILTER_HEADER_H:
        by1, by2 = row_bands[0]
        band_crop = binary[by1:by2, :]
        band_proj = np.sum(band_crop, axis=1) // 255
        gap_thresh = w * 0.005
        gap_start = -1
        for i in range(len(band_proj)):
            if band_proj[i] <= gap_thresh:
                if gap_start == -1:
                    gap_start = i
            else:
                if gap_start != -1 and i - gap_start >= SEG_HEADER_GAP_MIN:
                    split_y = by1 + gap_start + (i - gap_start) // 2
                    row_bands[0] = (split_y, by2)
                    break
                gap_start = -1

    questions = []
    q_idx = 0
    for ry1, ry2 in row_bands:
        row_img = binary[ry1:ry2, :]
        row_h_val = row_img.shape[0]

        v_kernel_w = max(3, w // SEG_V_KERNEL_W_DIV)
        v_kernel_h = max(3, int(row_h_val * SEG_V_KERNEL_H_RATIO))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (v_kernel_w, v_kernel_h))
        row_dilated = cv2.morphologyEx(row_img, cv2.MORPH_CLOSE, v_kernel)

        col_proj = np.sum(row_dilated, axis=0) // 255
        col_threshold = row_h_val * SEG_COL_THRESH_RATIO

        col_bands = []
        in_band = False
        start = 0
        min_col_w = max(20, w // SEG_MIN_COL_W_DIV)
        for j in range(len(col_proj)):
            if col_proj[j] > col_threshold and not in_band:
                start = j
                in_band = True
            elif col_proj[j] <= col_threshold and in_band:
                if j - start > min_col_w:
                    col_bands.append((start, j))
                in_band = False
        if in_band and len(col_proj) - start > min_col_w:
            col_bands.append((start, len(col_proj)))

        if not col_bands:
            col_bands = [(0, w)]
        elif len(col_bands) > 1:
            min_col_w_thresh = w * SEG_WIDE_COL_MIN_RATIO
            wide_cols = [b for b in col_bands if (b[1] - b[0]) >= min_col_w_thresh]
            if 1 <= len(wide_cols) <= 2:
                col_bands = wide_cols
            else:
                valid_width = sum(b[1]-b[0] for b in col_bands)
                if valid_width < w * SEG_VALID_COL_RATIO:
                    col_bands = [(0, w)]

        for cx1, cx2 in col_bands:
            x1 = max(0, cx1 - SEG_CROP_PAD)
            x2 = min(w, cx2 + SEG_CROP_PAD)
            y1 = max(0, ry1 - SEG_CROP_PAD)
            y2 = min(h, ry2 + SEG_CROP_PAD)

            crop = img[y1:y2, x1:x2]
            if crop.shape[0] < SEG_MIN_CROP_H or crop.shape[1] < SEG_MIN_CROP_W:
                continue

            q_idx += 1
            questions.append({
                "idx": q_idx,
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
                "crop": crop,
            })

    return questions


def segment_multi_column_layout(img: np.ndarray, binary: np.ndarray, h: int, w: int) -> list:
    margin = max(1, w // 20)
    inner_gaps = _detect_column_gaps(binary, h, w)

    if not inner_gaps:
        return segment_single_column(img, binary, h, w)

    col_boundaries = [0]
    for gx1, gx2 in inner_gaps:
        mid = (gx1 + gx2) // 2
        col_boundaries.append(mid)
    col_boundaries.append(w)
    col_boundaries = sorted(set(col_boundaries))

    # Validate: drop columns that are too narrow, empty, or are actually the gaps
    valid_cols = []
    for ci in range(len(col_boundaries) - 1):
        cw = col_boundaries[ci + 1] - col_boundaries[ci]
        if cw < max(w * LAYOUT_COL_MIN_WIDTH_RATIO, SEG_MIN_CROP_W):
            continue
        # Skip columns that align with detected gaps
        col_x1, col_x2 = col_boundaries[ci], col_boundaries[ci + 1]
        gap_overlap = sum(max(0, min(col_x2, g[1]) - max(col_x1, g[0])) for g in inner_gaps)
        if gap_overlap > cw * 0.5:
            continue
        # Check column actually has content
        col_content_px = np.sum(binary[:, col_x1:col_x2])
        if col_content_px > h * cw * 0.01:
            valid_cols.append((col_x1, col_x2))
    if not valid_cols:
        valid_cols = [(0, w)]

    all_questions = []
    for col_idx, (cx1, cx2) in enumerate(valid_cols):
        col_binary = binary[:, cx1:cx2]
        col_img = img[:, cx1:cx2]
        col_w = cx2 - cx1
        qs = segment_single_column(col_img, col_binary, h, col_w)
        for q in qs:
            q["bbox"]["x"] += cx1
            q["_col"] = col_idx
        all_questions.extend(qs)

    # Re-index in reading order
    all_questions.sort(key=lambda q: (q.get("_col", 0), q["bbox"]["y"]))
    for new_idx, q in enumerate(all_questions, 1):
        q["idx"] = new_idx
        q.pop("_col", None)
    return all_questions


def segment_by_contours(img: np.ndarray, binary: np.ndarray, h: int, w: int) -> list:
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = h * w * LAYOUT_FREEFORM_AREA_RATIO

    raw_regions = []
    for cnt in contours:
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        if rh > SEG_CONTOUR_MIN_H and rw > SEG_CONTOUR_MIN_W and rh * rw > min_area:
            raw_regions.append((rx, ry, rw, rh))

    # Merge nearby regions (freeform items may be fragmented)
    raw_regions.sort(key=lambda r: (r[1], r[0]))
    merged = []
    for rx, ry, rw, rh in raw_regions:
        merged_with = False
        for mr in reversed(merged):
            mx, my, mw, mh = mr
            x_overlap = max(0, min(rx + rw, mx + mw) - max(rx, mx))
            y_gap = ry - (my + mh)
            if x_overlap > 0 and y_gap < SEG_FRAGMENT_GAP:
                mr[2] = max(mx + mw, rx + rw) - mr[0]
                mr[3] = max(my + mh, ry + rh) - mr[1]
                merged_with = True
                break
        if not merged_with:
            merged.append([rx, ry, rw, rh])

    # Prune regions contained by others
    protected = [True] * len(merged)
    for i in range(len(merged)):
        for j in range(len(merged)):
            if i != j and protected[i]:
                a = merged[i]
                b = merged[j]
                contains = (b[0] >= a[0] and b[1] >= a[1]
                            and b[0] + b[2] <= a[0] + a[2]
                            and b[1] + b[3] <= a[1] + a[3])
                if contains and (b[2] * b[3]) < (a[2] * a[3]) * 0.8:
                    protected[j] = False

    questions = []
    q_idx = 0
    for i, (rx, ry, rw, rh) in enumerate(merged):
        if not protected[i]:
            continue
        x1 = max(0, rx - SEG_CROP_PAD)
        x2 = min(w, rx + rw + SEG_CROP_PAD)
        y1 = max(0, ry - SEG_CROP_PAD)
        y2 = min(h, ry + rh + SEG_CROP_PAD)
        crop = img[y1:y2, x1:x2]
        if crop.shape[0] < SEG_MIN_CROP_H or crop.shape[1] < SEG_MIN_CROP_W:
            continue
        q_idx += 1
        questions.append({
            "idx": q_idx,
            "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
            "crop": crop,
        })

    return questions


def segment_questions(img: np.ndarray, layout_type: str = None) -> list:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    if layout_type is None:
        layout_type = detect_layout_type(img, binary)
    print(f"  Layout: {layout_type}")

    if layout_type in ("two-column", "multi-column"):
        questions = segment_multi_column_layout(img, binary, h, w)
        if not questions:
            print("  Multi-column gave 0 questions, falling back to single-column...")
            questions = segment_single_column(img, binary, h, w)
    elif layout_type == "freeform":
        questions = segment_by_contours(img, binary, h, w)
        if not questions:
            print("  Freeform contour gave 0 questions, falling back to single-column...")
            questions = segment_single_column(img, binary, h, w)
    else:
        questions = segment_single_column(img, binary, h, w)

    if not questions:
        print("  Primary segmentation gave 0 questions, trying contour fallback...")
        questions = segment_by_contours(img, binary, h, w)

    if questions:
        questions = filter_question_regions(questions, h, w)
        refined = []
        for q in questions:
            if q["bbox"]["height"] > SEG_RESEGMENT_THRESH:
                sub = resegment_region(img, q, h, w)
                refined.extend(sub)
            else:
                refined.append(q)
        refined = merge_fragments(refined, img_w=w)
        refined = deduplicate_overlaps(refined)
        refined = filter_question_regions(refined, h, w)
        for new_idx, q in enumerate(refined, 1):
            q["idx"] = new_idx
        questions = refined

    return questions


def resegment_region(img: np.ndarray, parent: dict, img_h: int, img_w: int) -> list:
    region = parent["crop"]
    rh, rw = region.shape[:2]
    gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    def _compute_bands(proj, threshold, min_row_h):
        bands = []
        in_band = False
        start = 0
        for i in range(len(proj)):
            if proj[i] > threshold and not in_band:
                start = i
                in_band = True
            elif proj[i] <= threshold and in_band:
                if i - start > min_row_h:
                    bands.append((start, i))
                in_band = False
        if in_band and len(proj) - start > min_row_h:
            bands.append((start, len(proj)))
        return bands

    # Pass 1: coarse kernel
    coarse_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rw // 3, max(3, rh // 120)))
    coarse_dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, coarse_kernel)
    coarse_proj = np.sum(coarse_dilated, axis=1) // 255
    threshold = rw * 0.01
    min_row_h = max(15, rh // SEG_MIN_ROW_H_DIV)
    row_bands = _compute_bands(coarse_proj, threshold, min_row_h)

    # Pass 2: finer kernel if coarse gave 1 tall undivided region
    finer_thresh = max(SEG_RESEGMENT_THRESH, int(SEG_RESEGMENT_THRESH * SEG_RESEGMENT_FINER_THRESH_FACTOR))
    if len(row_bands) <= 1 and rh >= finer_thresh:
        finer_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rw // 6, max(3, rh // 160)))
        finer_dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, finer_kernel)
        finer_proj = np.sum(finer_dilated, axis=1) // 255
        row_bands = _compute_bands(finer_proj, threshold, min_row_h)

    # If row projection still gave 1 band, try grid-aware column splitting
    if len(row_bands) <= 1 and rh >= SEG_RESEGMENT_THRESH:
        col_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, rw // 80), rh // 4))
        col_dilated = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, col_kernel)
        col_proj = np.sum(col_dilated, axis=0) // 255
        col_thresh = rh * 0.02
        col_bands = _compute_bands(col_proj, col_thresh, max(10, rw // 60))
        # Keep only reasonably wide columns (not noise)
        grid_cols = [b for b in col_bands if (b[1] - b[0]) > max(30, rw * 0.08)]
        if len(grid_cols) >= 2:
            row_bands = _compute_bands(
                np.sum(dilated, axis=1) // 255, rw * 0.01, max(15, rh // SEG_MIN_ROW_H_DIV)
            )
            if len(row_bands) >= 2:
                results = []
                for ry1, ry2 in row_bands:
                    for cx1, cx2 in grid_cols:
                        x1 = max(0, px + cx1 - 2)
                        x2 = min(img_w, px + cx2 + 2)
                        y1 = max(0, py + ry1 - 3)
                        y2 = min(img_h, py + ry2 + 3)
                        crop = img[y1:y2, x1:x2]
                        if crop.shape[0] < 20 or crop.shape[1] < 20:
                            continue
                        results.append({
                            "idx": 0,
                            "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
                            "crop": crop,
                        })
                if results:
                    return results

    px, py = parent["bbox"]["x"], parent["bbox"]["y"]
    results = []
    for ry1, ry2 in row_bands:
        x1 = max(0, px - 2)
        x2 = min(img_w, px + rw + 2)
        y1 = max(0, py + ry1 - 3)
        y2 = min(img_h, py + ry2 + 3)
        crop = img[y1:y2, x1:x2]
        if crop.shape[0] < 20 or crop.shape[1] < 20:
            continue
        results.append({
            "idx": 0,
            "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
            "crop": crop,
        })

    if not results:
        results.append(parent)
    return results


def merge_fragments(regions: list, img_w: int = 0) -> list:
    merged = []
    i = 0
    while i < len(regions):
        cur = regions[i]
        cb = cur["bbox"]
        is_instruction = img_w > 0 and _is_instruction_line(cb, img_w)
        is_fragment = not is_instruction and (cb["height"] < SEG_FRAGMENT_H or (cb["height"] < SEG_FRAGMENT_H2 and cb["width"] > SEG_FRAGMENT_ASPECT * cb["height"]))
        if is_fragment and i + 1 < len(regions):
            nxt = regions[i + 1]
            nb = nxt["bbox"]
            gap = nb["y"] - (cb["y"] + cb["height"])
            if gap < SEG_FRAGMENT_GAP:
                ny = cb["y"]
                nh = (nb["y"] + nb["height"]) - ny
                nw = max(cb["width"], nb["width"])
                nx = min(cb["x"], nb["x"])
                merged.append({
                    "idx": 0,
                    "bbox": {"x": nx, "y": ny, "width": nw, "height": nh},
                    "crop": None,
                })
                i += 2
                continue
        if is_fragment and merged:
            prev = merged[-1]
            pb = prev["bbox"]
            gap = cb["y"] - (pb["y"] + pb["height"])
            if gap < SEG_FRAGMENT_GAP:
                merged_bbox = {
                    "x": min(pb["x"], cb["x"]),
                    "y": pb["y"],
                    "width": max(pb["width"], cb["width"]),
                    "height": (cb["y"] + cb["height"]) - pb["y"],
                }
                prev["bbox"] = merged_bbox
                i += 1
                continue
        merged.append(cur)
        i += 1
    return merged


def deduplicate_overlaps(regions: list) -> list:
    if not regions:
        return regions
    kept = []
    sorted_regions = sorted(regions, key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))
    for r in sorted_regions:
        b = r["bbox"]
        overlap_found = False
        for k in kept:
            kb = k["bbox"]
            x_overlap = max(0, min(b["x"] + b["width"], kb["x"] + kb["width"]) - max(b["x"], kb["x"]))
            y_overlap = max(0, min(b["y"] + b["height"], kb["y"] + kb["height"]) - max(b["y"], kb["y"]))
            if x_overlap > 0 and y_overlap > 0:
                overlap_ratio = (x_overlap * y_overlap) / min(b["width"] * b["height"], kb["width"] * kb["height"])
                if overlap_ratio > 0.5:
                    overlap_found = True
                    break
        if not overlap_found:
            kept.append(r)
    return kept


def _is_instruction_line(bbox: dict, img_w: int) -> bool:
    return bbox["height"] < SEG_FRAGMENT_H and bbox["width"] > img_w * SEG_INSTRUCTION_MIN_WIDTH_RATIO


def filter_question_regions(questions: list, img_h: int, img_w: int) -> list:
    filtered = []
    for q in questions:
        b = q["bbox"]
        region_top_ratio = b["y"] / img_h
        region_bottom_ratio = (b["y"] + b["height"]) / img_h
        aspect = b["width"] / max(b["height"], 1)
        area = b["width"] * b["height"]
        img_area = img_w * img_h
        area_ratio = area / img_area

        is_instruction_line = _is_instruction_line(b, img_w)
        is_header = region_top_ratio < SEG_FILTER_HEADER_TOP and (b["height"] < SEG_FILTER_HEADER_H or (aspect > SEG_FILTER_HEADER_ASPECT and b["height"] < SEG_FILTER_HEADER_H2))
        is_footer = region_bottom_ratio > SEG_FILTER_FOOTER_BOT and b["height"] < SEG_FILTER_FOOTER_H
        is_bottom_strip = region_bottom_ratio > SEG_FILTER_BOTTOM_STRIP_BOT and b["height"] < SEG_FILTER_BOTTOM_STRIP_H
        is_too_small = area_ratio < SEG_FILTER_SMALL_AREA and (b["height"] < SEG_FILTER_SMALL_H or b["width"] < SEG_FILTER_SMALL_W)
        is_noise = b["height"] < SEG_FILTER_NOISE_H or b["width"] < SEG_FILTER_NOISE_W

        if (is_instruction_line and not is_header) or not (is_header or is_footer or is_bottom_strip or is_too_small or is_noise):
            filtered.append(q)

    return filtered


_ROMAN_MAP = {
    'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8,
    'ix': 9, 'x': 10, 'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15,
}


def _to_number(val: str) -> int:
    # Try digit
    try:
        return int(val)
    except ValueError:
        pass
    # Try Roman (lowercase)
    roman_val = val.strip().lower()
    if roman_val in _ROMAN_MAP:
        return _ROMAN_MAP[roman_val]
    # Try letter (A=1, B=2, ..., Z=26)
    if len(val) == 1 and val.isalpha():
        return ord(val.upper()) - ord('A') + 1
    return 0


def _match_question_number(text: str) -> tuple:
    for pattern in Q_NUMBER_PATTERNS:
        m = re.match(pattern, text)
        if m:
            num = _to_number(m.group(1))
            if num > 0:
                return True, num, text[m.end():]
    return False, 0, text


def inherit_group_context(questions: list) -> list:
    for i, q in enumerate(questions):
        qt = q.get("question_text", "").strip()
        is_numbered, num, body = _match_question_number(qt)
        q["_numbered_prefix"] = is_numbered
        q["_prefix_num"] = num
        q["_body"] = body

    for i, q in enumerate(questions):
        has_verb = bool(q.get("instruction_verb", ""))
        if has_verb and q.get("_numbered_prefix", False):
            continue
        if not q["_numbered_prefix"] and not has_verb:
            for j in range(i - 1, -1, -1):
                prev = questions[j]
                if prev.get("_numbered_prefix", False):
                    prev_verb = prev.get("instruction_verb", "")
                    prev_text = prev.get("question_text", "")
                    if prev_verb:
                        q["instruction_verb"] = prev_verb
                        q["group_context"] = {
                            "is_grouped": True,
                            "group_id": prev["_prefix_num"],
                            "group_instruction": prev_text,
                        }
                    break

    for q in questions:
        q.pop("_numbered_prefix", None)
        q.pop("_prefix_num", None)
        q.pop("_body", None)
    return questions


def _extract_json(text: str) -> tuple:
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    cleaned = re.sub(r'```json\s*|```\s*', '', cleaned).strip()
    cleaned = re.sub(r'^[^{]+', '', cleaned)
    if not cleaned or cleaned[0] != '{':
        return None, "no JSON object found"
    brace_depth = 0
    end = -1
    for i, ch in enumerate(cleaned):
        if ch == '{':
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
        if brace_depth == 0:
            end = i + 1
            break
    if end == -1:
        return None, "unmatched braces"
    cleaned = cleaned[:end]

    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    cleaned_tc = re.sub(r',\s*}', '}', cleaned)
    cleaned_tc = re.sub(r',\s*]', ']', cleaned_tc)
    try:
        return json.loads(cleaned_tc), None
    except json.JSONDecodeError:
        pass

    cleaned_esc = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', '', cleaned)
    try:
        return json.loads(cleaned_esc), None
    except json.JSONDecodeError:
        pass

    return None, "could not parse JSON after all fallbacks"


def analyze_question(llm, img: np.ndarray, name: str) -> dict:
    if llm is None:
        return {"file": name, "raw": "", "parsed": None, "error": "llm is None", "attempts": 0}

    h_crop, w_crop = img.shape[:2]
    if min(h_crop, w_crop) > ANALYSIS_LARGE_CROP_WARN:
        est_tokens = (h_crop // 16) * (w_crop // 16)
        if est_tokens > 3000:
            print(f"\n    NOTE: Large crop ({w_crop}x{h_crop}, ~{est_tokens} img tokens) — may exceed context")

    _, buffer = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    b64 = base64.b64encode(buffer).decode("utf-8")

    best = {"file": name, "raw": "", "parsed": None, "error": "max retries exceeded", "attempts": 0}
    retry_hints = [
        "",
        "IMPORTANT: Return ONLY valid JSON. Extract ALL visible text, ALL objects, and ALL answer spaces. Do NOT include answer or expected_answer.",
        "CRITICAL: You MUST return valid JSON with every field. Use '' for text, [] for lists, {{}} for objects, 0 for numbers, false for booleans. Do NOT extract answers.",
    ]

    for attempt in range(1, ANALYSIS_MAX_RETRIES + 1):
        hint = retry_hints[min(attempt - 1, len(retry_hints) - 1)]
        user_text = QUESTION_EXTRACT_PROMPT
        if hint:
            user_text += "\n\n" + hint
        user_text += "\n\nAnalyze this single question crop. Extract everything visible."

        resp = llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": user_text},
                ],
            }],
            max_tokens=ANALYSIS_MAX_TOKENS, temperature=ANALYSIS_BASE_TEMP + (attempt - 1) * ANALYSIS_TEMP_STEP,
        )

        raw = resp["choices"][0]["message"]["content"]
        parsed, error = _extract_json(raw)

        if parsed and isinstance(parsed, dict):
            qt = str(parsed.get("question_text", "")).strip()
            qt_type = str(parsed.get("question_type", "")).strip()
            has_items = bool(parsed.get("items", []))
            has_objects = bool(parsed.get("objects", []))

            if qt or qt_type or has_items or has_objects:
                best = {"file": name, "raw": raw, "parsed": parsed, "error": None, "attempts": attempt}
                break
            best = {"file": name, "raw": raw, "parsed": parsed, "error": "all fields empty", "attempts": attempt}
        else:
            best = {"file": name, "raw": raw, "parsed": None, "error": error or "unknown", "attempts": attempt}

    return best


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


class QuestionPaperAnalyzer:
    def __init__(self, llm=None):
        self.llm = llm

    def load_gemma(self, model_path: str = None, cache_dir: str = "/root/gguf_cache"):
        if self.llm is not None:
            return

        from llama_cpp import Llama, llama_supports_gpu_offload
        from llama_cpp.llama_chat_format import Gemma4ChatHandler
        import torch

        os.makedirs(cache_dir, exist_ok=True)

        gpu_avail = torch.cuda.is_available()
        gpu_count = torch.cuda.device_count() if gpu_avail else 0

        if gpu_avail:
            for i in range(gpu_count):
                total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                print(f"  GPU {i}: {torch.cuda.get_device_name(i)} ({total:.0f} GB)")

        has_gpu = gpu_avail and llama_supports_gpu_offload()

        CHAT_HANDLER = Gemma4ChatHandler.from_pretrained(
            repo_id="unsloth/gemma-4-26B-A4B-it-GGUF",
            filename="mmproj-F16.gguf",
            local_dir=cache_dir, verbose=False,
        )

        if gpu_avail:
            total_vram = sum(torch.cuda.get_device_properties(i).total_memory for i in range(gpu_count))
            model_file = "gemma-4-26B-A4B-it-UD-Q5_K_XL.gguf" if total_vram >= 22 * (1024**3) else "gemma-4-26B-A4B-it-Q4_K_M.gguf"
            print(f"  Total VRAM: {total_vram/(1024**3):.0f} GB -> {model_file}")
        else:
            model_file = "gemma-4-26B-A4B-it-Q4_K_M.gguf"
            print(f"  No GPU detected -> {model_file} (CPU)")

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
        else:
            model_kwargs["n_gpu_layers"] = 0

        start = time.time()
        self.llm = Llama.from_pretrained(**model_kwargs)
        elapsed = (time.time() - start) / 60
        print(f"  Model loaded in {elapsed:.1f} min")

    def analyze_full_worksheet(self, img: np.ndarray) -> dict:
        if self.llm is None:
            return {"worksheet_structure": {}, "error": "llm is None"}

        _, buffer = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        b64 = base64.b64encode(buffer).decode("utf-8")

        prompt = """You are analyzing a FULL WORKSHEET. Identify the overall structure.

Return JSON:
{
  "total_question_count": 0,
  "layout_type": "single-column|two-column|three-column|mixed|grid|freeform",
  "has_header": true/false,
  "has_footer": true/false,
  "questions": [
    {
      "question_number": 1,
      "expected_position": "top-left|top-right|middle-left|middle-right|bottom-left|bottom-right|full-width",
      "has_illustration": true/false,
      "is_part_of_group": true/false,
      "group_id": 0,
      "group_instruction": ""
    }
  ],
  "shared_instructions": ["instruction 1", "instruction 2"],
  "answer_area_location": "within-questions|at-bottom|separate-sheet"
}"""

        resp = self.llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=ANALYSIS_MAX_TOKENS, temperature=ANALYSIS_BASE_TEMP,
        )

        raw = resp["choices"][0]["message"]["content"]
        parsed, _ = _extract_json(raw)
        return {"raw": raw, "parsed": parsed or {}}

    def process_image(self, image_path: str, output_dir: str = None,
                      save_crops: bool = True, use_full_worksheet_analysis: bool = False,
                      export_csv: bool = False) -> dict:
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

        start_time = time.time()
        processed_img, info = preprocess_image(img)
        if info["applied"]:
            print(f"  Preprocessing: {', '.join(info['applied'])}")
        else:
            print("  Preprocessing: none needed")

        if output_dir:
            enhanced_path = ws_dir / name
            cv2.imwrite(str(enhanced_path), cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))

        ws_context = {}
        if use_full_worksheet_analysis and self.llm is not None:
            print("  Analyzing full worksheet structure...", end=" ", flush=True)
            ws_analysis = self.analyze_full_worksheet(processed_img)
            ws_context = ws_analysis.get("parsed", {})
            print(f"detected {ws_context.get('total_question_count', '?')} questions, layout: {ws_context.get('layout_type', 'unknown')}")

        questions = segment_questions(processed_img)
        for q in questions:
            b = q["bbox"]
            q["crop"] = processed_img[b["y"]:b["y"]+b["height"], b["x"]:b["x"]+b["width"]]
        print(f"  Questions detected after filtering: {len(questions)}")

        if output_dir:
            debug_img = processed_img.copy()
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
            for qi, q in enumerate(questions):
                b = q["bbox"]
                color = colors[qi % len(colors)]
                cv2.rectangle(debug_img, (b["x"], b["y"]), (b["x"] + b["width"], b["y"] + b["height"]), color, 3)
                cv2.putText(debug_img, str(q["idx"]), (b["x"] + 4, b["y"] + 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            debug_path = ws_dir / f"{stem}_debug_bboxes.jpg"
            cv2.imwrite(str(debug_path), cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))

        worksheet_data = {
            "worksheet": name,
            "worksheet_info": {
                "width": int(img.shape[1]),
                "height": int(img.shape[0]),
                "preprocessing": info,
            },
            "worksheet_structure": ws_context if ws_context else {},
            "questions": []
        }

        for q in questions:
            q_idx = q["idx"]
            crop_name = f"{stem}_q{q_idx}.png"
            print(f"  [{q_idx}/{len(questions)}] Analyzing...", end=" ", flush=True)

            if output_dir and save_crops:
                try:
                    crop_path = crops_dir / crop_name
                    cv2.imwrite(str(crop_path), cv2.cvtColor(q["crop"], cv2.COLOR_RGB2BGR))
                except Exception as e:
                    print(f"\n    WARN: could not save crop {crop_name}: {e}")

            try:
                result = analyze_question(self.llm, q["crop"], crop_name)
            except Exception as e:
                result = {"file": crop_name, "raw": "", "parsed": None, "error": str(e), "attempts": 0}

            spec = result.get("parsed") or {}
            confidence = 1.0 - (result["attempts"] - 1) * 0.1 if result["parsed"] else 0.0
            confidence = max(0.0, min(1.0, confidence))

            group_info = spec.get("group_context", {})
            if not group_info and ws_context and ws_context.get("questions"):
                for wq in ws_context["questions"]:
                    if wq.get("question_number") == q_idx:
                        group_info = {
                            "is_grouped": wq.get("is_part_of_group", False),
                            "group_id": wq.get("group_id", 0),
                            "group_instruction": wq.get("group_instruction", ""),
                        }
                        break

            entry = {
                "question_number": q_idx,
                "bounding_box": q["bbox"],
                "analysis_attempts": result["attempts"],
                "analysis_error": result["error"],
                "confidence": round(confidence, 2),
                "raw_response": result.get("raw", "") if result.get("raw") else "",
                "question_text": spec.get("question_text", ""),
                "all_visible_text": spec.get("all_visible_text", []),
                "instruction_verb": spec.get("instruction_verb", ""),
                "question_type": spec.get("question_type", ""),
                "question_sub_type": spec.get("question_sub_type", ""),
                "structure": spec.get("structure", ""),
                "item_count": spec.get("item_count", 0),
                "items": spec.get("items", []),
                "objects": spec.get("objects", []),
                "total_object_count": spec.get("total_object_count", 0),
                "illustration_purpose": spec.get("illustration_purpose", ""),
                "answer_spaces": spec.get("answer_spaces", []),
                "visual_elements": spec.get("visual_elements", []),
                "colors_mentioned": spec.get("colors_mentioned", []),
                "relational_words": spec.get("relational_words", []),
                "group_context": group_info,
                "concept": spec.get("concept", ""),
                "learning_outcome": spec.get("learning_outcome", ""),
                "cognitive_skill": spec.get("cognitive_skill", ""),
                "motor_skill": spec.get("motor_skill", ""),
                "difficulty": spec.get("difficulty", ""),
            }
            worksheet_data["questions"].append(entry)

            qt = entry["question_text"][:60] if entry["question_text"] else "[empty]"
            qt_type = entry["question_type"] or "[unknown]"
            attempts = entry["analysis_attempts"]
            print(f"Q{q_idx}: {qt_type} | {qt} (attempts={attempts})")

            # Checkpoint: save after each question
            if output_dir:
                cp_path = ws_dir / f"{stem}_questions.json"
                with open(cp_path, "w", encoding="utf-8") as f:
                    json.dump(worksheet_data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        # Inherit group context: propagate instruction_verb and group_context to sub-questions
        worksheet_data["questions"] = inherit_group_context(worksheet_data["questions"])

        elapsed = time.time() - start_time
        print(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")

        if output_dir and export_csv:
            csv_path = ws_dir / f"{stem}_questions.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["question_number", "question_text", "question_type", "question_sub_type",
                                 "instruction_verb", "structure", "item_count", "total_object_count",
                                 "illustration_purpose", "concept", "cognitive_skill", "motor_skill",
                                 "difficulty", "confidence", "analysis_attempts", "analysis_error"])
                for qe in worksheet_data["questions"]:
                    writer.writerow([
                        qe["question_number"],
                        qe["question_text"][:200],
                        qe["question_type"],
                        qe["question_sub_type"],
                        qe["instruction_verb"],
                        qe["structure"],
                        qe["item_count"],
                        qe["total_object_count"],
                        qe["illustration_purpose"],
                        qe["concept"],
                        qe["cognitive_skill"],
                        qe["motor_skill"],
                        qe["difficulty"],
                        qe["confidence"],
                        qe["analysis_attempts"],
                        qe["analysis_error"],
                    ])
            print(f"  CSV: {csv_path}")

        return worksheet_data

    def process_batch(self, input_paths: list, output_dir: str = None,
                      save_crops: bool = True, use_full_worksheet_analysis: bool = False,
                      export_csv: bool = False) -> list:
        all_results = []
        batch_start = time.time()
        for i, path in enumerate(input_paths, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(input_paths)}] {Path(path).name}")
            print(f"{'='*60}")
            img_start = time.time()
            result = self.process_image(
                path, output_dir=output_dir, save_crops=save_crops,
                use_full_worksheet_analysis=use_full_worksheet_analysis,
                export_csv=export_csv,
            )
            img_elapsed = time.time() - img_start
            batch_elapsed = time.time() - batch_start
            avg = batch_elapsed / i
            remaining = avg * (len(input_paths) - i)
            print(f"  Time: {img_elapsed:.0f}s | Avg: {avg:.0f}s/img | ETA: {remaining/60:.0f}min")
            all_results.append(result)
        print(f"\n  Total batch time: {(time.time()-batch_start)/60:.1f}min")
        return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Question Paper Analyzer v2 — extract everything inside each question from worksheet images"
    )
    parser.add_argument("--input", "-i", required=True, nargs="+",
                        help="Input worksheet image(s) or directory")
    parser.add_argument("--output", "-o", default="./FLN_Results",
                        help="Output directory (default: ./FLN_Results)")
    parser.add_argument("--no-crops", action="store_true",
                        help="Don't save individual question crop images")
    parser.add_argument("--no-model", action="store_true",
                        help="Skip model loading (dry run — segmentation only)")
    parser.add_argument("--full-analysis", action="store_true",
                        help="Enable two-stage analysis: full worksheet first, then per-question")
    parser.add_argument("--csv", action="store_true",
                        help="Export CSV summary alongside JSON output")

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

    extractor = QuestionPaperAnalyzer()

    if not args.no_model:
        print("Loading Gemma 4 26B...")
        extractor.load_gemma()
    else:
        print("Skipping model load (dry run mode)")

    results = extractor.process_batch(
        [str(p) for p in input_paths],
        output_dir=args.output,
        save_crops=not args.no_crops,
        use_full_worksheet_analysis=args.full_analysis,
        export_csv=args.csv,
    )

    report_path = Path(args.output) / "all_questions_complete.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"worksheets": results}, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    total_qs = sum(len(r["questions"]) for r in results)
    print(f"\n{'='*60}")
    print(f"COMPLETE: {len(results)} worksheet(s), {total_qs} questions extracted")
    print(f"Combined output: {report_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

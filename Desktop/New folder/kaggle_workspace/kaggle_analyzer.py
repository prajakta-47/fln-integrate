#!/usr/bin/env python3
"""
Kaggle Gemma 4 26B Worksheet Analyzer
Phase 2 of the FLN pipeline — fills in the 20-field question specification
for each pre-segmented crop using Gemma 4 26B A4B via llama-cpp-python.

Usage (in Kaggle notebook):
    from kaggle_analyzer import GemmaWorksheetAnalyzer
    analyzer = GemmaWorksheetAnalyzer()
    analyzer.load_gemma()
    analyzer.analyze_all("workspace_results/all_questions_consolidated.json")
"""

import os, sys, json, cv2, numpy as np, base64, re, time
from pathlib import Path


QUESTION_SPEC_PROMPT = """You are an FLN Curriculum Intelligence Engine.
Look at this SINGLE QUESTION CROP from a children's worksheet (Grades 1-3).

Extract the COMPLETE QUESTION SPECIFICATION — every structural detail.
Ignore the answer. Focus on understanding the question itself.

--- FIELDS TO EXTRACT ---

1. question_text: The EXACT question text from the crop. If the crop contains no text, return "".

2. instruction_verb: Main action word(s): Count, Match, Circle, Colour, Write, Trace, Tick, Draw, Join, Add, Subtract, Cut, Paste, Read, Identify, etc.

3. question_type: Primary category e.g. Counting, Number Recognition, Addition, Subtraction, Matching, Colouring, Tracing, Pattern Completion, Odd One Out, Before-After-Between, Comparison, Place Value, Word Problem, Shape Recognition, Time, Money, Letter Recognition, Word Formation, Rhyming Words, Fill in the Blank, Sequencing, Sorting.

4. question_sub_type: More specific: Count-And-Write, Count-And-Circle, Count-And-Match, Colour-The-Number, Circle-The-Correct, Match-Number-To-Word, Match-Picture-To-Number, Join-Dots, Fill-Missing-Number, Tens-And-Ones, etc.

5. question_structure: standalone, grouped-under-instruction, matrix, matching-columns, table, grid, fill-in-series, horizontal-row, vertical-column, two-column, with-illustration, text-only.

6. objects: List every distinct object/illustration/item: [{"name": str, "count": int, "attributes": [str]}]. Empty list if no objects.

7. total_object_count: Total individual items. 0 if no countable objects.

8. illustration_arrangement: row, column, grid, scattered, grouped-by-type, circular, random, inside-frame, around-text. "" if no illustration.

9. illustration_purpose: counting, identification, matching, comparison, context-for-story, visual-discrimination. "" if none.

10. concept: FLN concept name e.g. "Counting 1-10", "Addition within 10", "Number Recognition 1-20", "Letter A-M", "Shape Identification".

11. learning_outcome: Measurable e.g. "Count objects up to 10 and write the number", "Recognize numbers 1-10".

12. cognitive_skill: Remembering, Understanding, Applying, or Analyzing.

13. motor_skill: Writing, Circling, Matching, Colouring, Tracing, Drawing, Tick-Marking, or Speaking.

14. difficulty: Easy, Medium, or Hard.

15. reasoning_required: Brief description of thinking process.

16. variables: What varies if repeated: ["number ranges", "object types", "letter cases", "position"].

17. template_pattern: Reusable template e.g. "Count [X] objects and write the number". "" if none.

18. answer_space: {"type": "blank|box|circle|line|box-to-write|empty-cell|colour-area|match-line|tick-box", "count": 0, "location": "below|beside|inside|at-end|replace-placeholder"}

19. visual_elements: List of structural components: ["border", "dotted-line", "arrow", "number-label", "icon", "table", "frame", "shading"]. Empty list if none.

20. sub_questions: If multiple items, list each: [{"sub_id": int, "text": "", "objects": [], "expected_value": ""}]. Empty list if not applicable.

--- OUTPUT ---
Return ONLY valid JSON with all 20 fields present. No markdown, no explanation.
question_text must be verbatim from image. Default empty strings or empty lists as appropriate.
Do NOT extract the answer. Focus only on question specification."""


def extract_json(text: str) -> tuple:
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    cleaned = re.sub(r'```json\s*|```\s*', '', cleaned).strip()
    cleaned = re.sub(r'^[^{]*', '', cleaned)
    cleaned = re.sub(r'[^}]*$', '', cleaned)
    if not cleaned:
        return None, "no JSON object found"
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
    if '}{' in cleaned:
        parts = cleaned.split('}{')
        for i in range(len(parts)):
            candidate = parts[i]
            if i > 0: candidate = '{' + candidate
            if i < len(parts) - 1: candidate = candidate + '}'
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError:
                continue
    return None, "could not parse JSON after all fallbacks"


class GemmaWorksheetAnalyzer:
    def __init__(self):
        self.llm = None

    def load_gemma(self, cache_dir: str = "/root/gguf_cache"):
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
        if gpu_avail and not has_gpu:
            print("  WARNING: GPUs detected but llama-cpp-python NOT built with CUDA support.")
        print("  Loading Gemma4ChatHandler...")
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
            print(f"  No GPU -> {model_file} (CPU - very slow)")
        model_kwargs = dict(
            repo_id="unsloth/gemma-4-26B-A4B-it-GGUF", filename=model_file,
            local_dir=cache_dir, chat_handler=CHAT_HANDLER, n_ctx=8192, verbose=False,
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
        print(f"  Loading {model_file}...")
        start = time.time()
        self.llm = Llama.from_pretrained(**model_kwargs)
        elapsed = (time.time() - start) / 60
        print(f"  Model loaded in {elapsed:.1f} min")

    def analyze_crop(self, crop_img: np.ndarray, crop_name: str, max_retries: int = 3) -> dict:
        if self.llm is None:
            return {"crop": crop_name, "error": "model not loaded", "spec": None}
        _, buffer = cv2.imencode(".png", cv2.cvtColor(crop_img, cv2.COLOR_RGB2BGR))
        b64 = base64.b64encode(buffer).decode("utf-8")
        result = {"crop": crop_name, "error": "max retries", "spec": None, "attempts": 0}
        for attempt in range(1, max_retries + 1):
            prompt = QUESTION_SPEC_PROMPT
            if attempt > 1:
                prompt += "\n\nIMPORTANT: Return ONLY valid JSON with all 20 fields. Both question_text and question_type must be non-empty."
            try:
                resp = self.llm.create_chat_completion(
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ]}],
                    max_tokens=2048, temperature=0.1 + (attempt-1)*0.1,
                )
                raw = resp["choices"][0]["message"]["content"]
            except Exception as e:
                result = {"crop": crop_name, "error": str(e), "spec": None, "attempts": attempt}
                continue
            parsed, error = extract_json(raw)
            if parsed and isinstance(parsed, dict):
                qt = str(parsed.get("question_text", "")).strip()
                if qt:
                    result = {"crop": crop_name, "error": None, "spec": parsed, "raw": raw, "attempts": attempt}
                    break
                result = {"crop": crop_name, "error": "empty question_text", "spec": parsed, "raw": raw, "attempts": attempt}
            else:
                result = {"crop": crop_name, "error": error or "parse failed", "spec": None, "raw": raw, "attempts": attempt}
        return result

    def analyze_all(self, consolidated_path: str, output_path: str = None, results_dir: str = None):
        with open(consolidated_path, encoding="utf-8") as f:
            questions = json.load(f)
        base = Path(consolidated_path).parent if results_dir is None else Path(results_dir)
        if output_path is None:
            output_path = str(base / "all_questions_analyzed.json")
        print(f"Loaded {len(questions)} questions from {consolidated_path}")
        total = len(questions)
        analyzed = []
        start_time = time.time()
        for i, q in enumerate(questions, 1):
            crop_rel = q["crop_path"]
            crop_abs = str(base.parent / crop_rel) if not os.path.isabs(crop_rel) else crop_rel
            qn = q["question_number"]
            ws = Path(q["worksheet"]).stem
            if not os.path.exists(crop_abs):
                print(f"  [{i}/{total}] Q{qn:2d} ({ws}) SKIP — crop not found: {crop_abs}")
                entry = q.copy()
                entry["analysis_error"] = "crop_not_found"
                entry["analysis_attempts"] = 0
                analyzed.append(entry)
                continue
            img = cv2.imread(crop_abs)
            if img is None:
                print(f"  [{i}/{total}] Q{qn:2d} ({ws}) SKIP — cannot read crop")
                entry = q.copy()
                entry["analysis_error"] = "cannot_read_crop"
                entry["analysis_attempts"] = 0
                analyzed.append(entry)
                continue
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            print(f"  [{i}/{total}] Q{qn:2d} ({ws}) {img_rgb.shape[1]}x{img_rgb.shape[0]}...", end=" ", flush=True)
            result = self.analyze_crop(img_rgb, f"Q{qn:02d}_{ws}.png")
            entry = q.copy()
            if result["spec"]:
                entry["analysis_error"] = result["error"]
                entry["analysis_attempts"] = result["attempts"]
                entry["analysis_raw"] = result.get("raw", "")
                entry["question_spec"] = result["spec"]
                print(f"OK ({result['attempts']} attempt(s))")
            else:
                entry["analysis_error"] = result["error"]
                entry["analysis_attempts"] = result["attempts"]
                entry["analysis_raw"] = result.get("raw", "")
                print(f"FAIL: {result['error']}")
            analyzed.append(entry)
            if i % 10 == 0:
                elapsed = time.time() - start_time
                per_q = elapsed / i
                remaining = per_q * (total - i)
                print(f"  --- {i}/{total} done ({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining) ---")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(analyzed, f, indent=2, ensure_ascii=False)
        success = sum(1 for a in analyzed if a.get("analysis_error") is None and a["question_spec"].get("question_text"))
        partial = sum(1 for a in analyzed if a.get("analysis_error") and not a.get("analysis_error") in ("crop_not_found", "cannot_read_crop"))
        failed = sum(1 for a in analyzed if a.get("analysis_error") in ("crop_not_found", "cannot_read_crop"))
        print(f"\n{'='*50}")
        print(f"  COMPLETE: {success} success, {partial} partial, {failed} failed")
        print(f"  Output: {output_path}")
        print(f"{'='*50}")
        return analyzed


if __name__ == "__main__":
    analyzer = GemmaWorksheetAnalyzer()
    analyzer.load_gemma()
    analyzer.analyze_all("workspace_results/all_questions_consolidated.json")

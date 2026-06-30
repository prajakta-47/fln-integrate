# Pipeline Guide — Step by Step

This guide walks through each stage of the FLN Worksheet Analysis Pipeline.

---

## Stage 1: Extract Images from .docx

**Script:** `image_extraction_from_docx/extract_images.py`

Place `.docx` files in `image_extraction_from_docx/`, then run:

```bash
python run_pipeline.py --stage 1
```

Or directly:

```bash
python image_extraction_from_docx/extract_images.py
```

**What it does:**
- Parses the `.docx` (a ZIP archive) to find all embedded images (`<a:blip>` elements)
- Preserves the **document order** of images
- Saves images as `image_001.png`, `image_002.jpg`, etc. in a subfolder named after the `.docx` file (e.g., `1.0/`)

---

## Stage 2: Package Images for Kaggle

**Script:** `run_pipeline.py` (Stage 2)

```bash
python run_pipeline.py --stage 2
```

**What it does:**
- Collects all extracted images (from Stage 1 subfolders)
- Also includes images from `manual_input/` if present (for direct image uploads)
- Copies them into `kaggle_input/` with numbered names (`image1.png`, `image2.jpg`, ...)
- Creates `kaggle_input.zip` for upload to Kaggle

---

## Stage 3 (Manual): Run Kaggle Notebook

**Notebook:** `gemma26b-image-metrics-illustrator.ipynb`

1. Go to [Kaggle](https://kaggle.com) and create a new notebook
2. **Settings → Accelerator → GPU T4 x2**
3. **Add-ons → Secrets → Add Secret** — key: `HF_TOKEN`, value: your Hugging Face token
4. Copy the notebook contents into Kaggle (or upload the `.ipynb` file)
5. **Add Data** → Upload `kaggle_input.zip`
6. **Cell → Run All**
7. Wait ~15 min for the first run (model download), ~2–5 min for subsequent runs
8. Download the output: `FLN_Results.zip` from Kaggle working directory

**Output structure** (after extracting `FLN_Results.zip`):
```
FLN_Results/
├── image1.png
├── image1_result.json
├── image2.jpg
├── image2_result.json
└── ...
```

---

## Stage 3 (Local): Process Kaggle Results

```bash
# Extract FLN_Results.zip into kaggle_results/
# Then run:
python run_pipeline.py --stage 3
```

**What it does:**
- Reads images and `*_result.json` files from `kaggle_results/`
- Creates per-image folders in `structure_img_with_question/data/`
- Copies image and JSON into each folder
- Generates `data/batch_manifest.json` with file list and metadata

---

## Stage 4: Generate HTML Report

**Script:** `structure_img_with_question/generate_report.py`

```bash
python run_pipeline.py --stage 4
```

Or directly:

```bash
python structure_img_with_question/generate_report.py
```

**What it does:**
- Reads `data/batch_manifest.json` and all `*_result.json` files
- Builds an HTML page with:
  - **Card per question** — type badge, grade badge, confidence score
  - **Image preview** — embedded as base64
  - **Question heading** — extracted from analysis
  - **Instruction text** — intelligently selected from `student_action` or `all_text_detected`
- Outputs `structure_img_with_question/question_report.html`
- Open in any browser — fully offline (no external assets)

---

## Running the Full Pipeline

```bash
# 1–2: Extract + Package
python run_pipeline.py

# 3: (Manual) Kaggle notebook

# 4–5: Process + Report
python run_pipeline.py
```

The pipeline script skips stages gracefully if prerequisites are missing.

---

## Customization

### Adding images without .docx
Place `.png` or `.jpg` files in a `manual_input/` folder at the pipeline root. Stage 2 will pick them up automatically.

### Skipping the packaging step
Place images directly in `kaggle_input/` and zip them manually. Then skip Stage 2.

### Running only new images
Move already-processed JSON/image pairs out of `data/` and re-run Stage 3. The manifest is regenerated fresh each time.

# FLN Worksheet Analysis Pipeline

End-to-end pipeline for extracting, analyzing, and reporting on FLN (Foundational Literacy and Numeracy) worksheets.

## Pipeline Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  STAGE 1     │    │  STAGE 2     │    │  STAGE 3     │    │  STAGE 4     │
│  EXTRACT     │───>│  PACKAGE     │───>│  PROCESS     │───>│  REPORT      │
│  .docx→images│    │  images→zip  │    │  Kaggle JSON │    │  HTML report │
└──────────────┘    └──────────────┘    └──────┬───────┘    └──────────────┘
                                               │
                                        ┌──────┴───────┐
                                        │  Kaggle      │
                                        │  Notebook    │
                                        │  (Manual)    │
                                        └──────────────┘
```

### Stages

| Stage | Component | Description |
|-------|-----------|-------------|
| 1 | `image_extraction_from_docx/extract_images.py` | Extracts images from `.docx` files in document order (zero deps) |
| 2 | `run_pipeline.py --stage 2` | Packages images into `kaggle_input.zip` for Kaggle upload |
| — | `gemma26b-image-metrics-illustrator.ipynb` | **Kaggle notebook** — analyzes images via Gemma 4 26B Vision (run manually) |
| 3 | `run_pipeline.py --stage 3` | Organizes Kaggle results into `structure_img_with_question/data/` with manifest |
| 4 | `structure_img_with_question/generate_report.py` | Generates offline `question_report.html` with image + metadata cards |

## Quick Start

```bash
# 1. Extract images from .docx
python run_pipeline.py --stage 1

# 2. Package images for Kaggle
python run_pipeline.py --stage 2

# 3. Upload kaggle_input.zip → Kaggle, run notebook, download FLN_Results.zip
#    → Extract to kaggle_results/

# 4. Process Kaggle results
python run_pipeline.py --stage 3

# 5. Generate HTML report
python run_pipeline.py --stage 4

# Or run everything (except Kaggle notebook)
python run_pipeline.py
```

## Directory Layout

```
complete pipeline/
├── run_pipeline.py                    # Orchestration script
├── README.md                          # This file
├── SETUP.md                           # Detailed setup instructions
├── PIPELINE_GUIDE.md                   # Step-by-step pipeline walkthrough
│
├── image_extraction_from_docx/        # Stage 1: extract images from .docx
│   ├── extract_images.py
│   ├── 1.0.docx                       # Input docx files
│   └── 1.0/                           # Extracted images (auto-generated)
│       └── image_001.png
│
├── structure_img_with_question/       # Stage 3 & 4: process results & generate report
│   ├── generate_report.py
│   ├── generate_paper.py
│   ├── question_report.html           # Final output
│   ├── question_paper.html
│   ├── question_template.html
│   ├── a.html
│   └── data/                          # Structured data (auto-generated)
│       ├── batch_manifest.json
│       ├── image1/
│       │   ├── image1.png
│       │   └── image1_result.json
│       └── ...
│
├── kaggle_results/                    # Unpack Kaggle output here
├── kaggle_input/                      # Temp — images for zipping
└── kaggle_input.zip                   # Upload this to Kaggle
```

## Requirements

- Python 3.10+
- **Zero pip dependencies** for local scripts (uses stdlib only)
- Kaggle account + GPU (T4 x2) for the notebook
- Gemma 4 26B model (gated — requires Hugging Face token)

## Related Repositories

- `fln_ai/` — Python package for the FLN Knowledge Extraction Engine (Phase 1, full pipeline with layout detection, segmentation, and database)
- `sidewise_pipeline/` — Kaggle notebook pipeline for sidewise worksheet analysis using Gemma 4 26B
- `question_paper_question_extract/` — Standalone question extraction and analysis scripts

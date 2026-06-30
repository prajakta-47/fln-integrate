# Setup Instructions

## Local Environment

### Prerequisites
- Python 3.10 or higher
- Git (optional)

### Installation

The local scripts use **zero external dependencies** — only Python standard library:
- `zipfile`, `xml.etree.ElementTree`, `pathlib` — for `extract_images.py`
- `json`, `base64`, `pathlib` — for `generate_report.py`
- `argparse`, `shutil`, `zipfile`, `json`, `pathlib` — for `run_pipeline.py`

```bash
# Clone or navigate to the project
cd "complete pipeline"

# Verify Python
python --version   # Should be 3.10+

# No pip install needed
```

### Verify Setup

```bash
# Test extraction script
python -c "from pathlib import Path; import sys; sys.path.insert(0, 'image_extraction_from_docx'); from extract_images import extract_images_in_order; print('extract_images.py OK')"

# Test report generator
python -c "from pathlib import Path; import sys; sys.path.insert(0, 'structure_img_with_question'); import generate_report; print('generate_report.py OK')"

# Test pipeline script
python run_pipeline.py --help
```

---

## Kaggle Environment

### Kaggle Notebook Setup

1. **Create a Kaggle account** at [kaggle.com](https://kaggle.com)
2. **Create a new notebook** with GPU:
   - Settings → Accelerator → **GPU T4 x2**
3. **Add Hugging Face token**:
   - Add-ons → Secrets → Add Secret
   - Key: `HF_TOKEN`
   - Value: your [Hugging Face access token](https://huggingface.co/settings/tokens)
4. **Upload input data**:
   - Click "Add Data" → Upload → select `kaggle_input.zip`
5. **Upload the notebook**:
   - File → Import Notebook → select `gemma26b-image-metrics-illustrator.ipynb`

### Model Notes
- **Model:** Gemma 4 26B A4B (Mixture-of-Experts, ~4B active params)
- **Format:** GGUF (~17 GB download on first run, cached at `/root/gguf_cache/`)
- **Runtime:** ~15 min first run, ~2–5 min subsequent runs
- **VRAM:** Uses both T4 GPUs (32 GB total) via llama.cpp multi-GPU
- **Hugging Face access** is required — the model is gated

---

## File Structure Checklist

```
complete pipeline/
├── run_pipeline.py            ✓ Orchestration script
├── image_extraction_from_docx/
│   ├── extract_images.py      ✓ Extraction logic
│   └── *.docx                 ← Place your docx files here
├── structure_img_with_question/
│   ├── generate_report.py     ✓ Report generation
│   ├── question_report.html   ← Final output
│   └── data/                  ← Structured data (auto-generated)
├── kaggle_results/            ← Extract Kaggle output here
├── kaggle_input/              ← Auto-generated (packaged images)
└── kaggle_input.zip           ← Auto-generated (upload to Kaggle)
```

> **Tip:** The first time you run the Kaggle notebook, the GGUF model must download (~17 GB). Start it before a break or lunch.

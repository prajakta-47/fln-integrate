# FLN Worksheet Generation Project

## Overview
Automated pipeline to generate **Foundational Literacy and Numeracy (FLN)** math worksheets for **Classes 1–3** (Indian NCF curriculum). The system scrapes illustration images from the web, converts them to B&W stickfigure-style line art, generates question text via LLM, and produces copy-paste-ready HTML tables and DOCX files.

## Skill Graph (Levels 1–32)

| Level | Topic | Sub-levels |
|-------|-------|------------|
| 1–11 | *(Class 1–2 basics: count 1–9, compare, shapes, etc.)* | — |
| **12** | **Place Value (Numbers 11–30)** — Tens & Ones with 🟦🟨 blocks | .0 Mastery, .1 Easier, .2 Remedial |
| **13** | **Number Line (11–30)** — Fill missing numbers | .0 Mastery, .1 Easier, .2 (template) |
| **14** | *(empty templates — not populated)* | .0, .1, .2 |
| **15** | **Before / Between / After (1–30)** | .0 Mastery, .1 Easier |
| **16** | **Addition (1–30)** — Objects + Numerals | .0 Mastery, .1 Easier, .2 Remedial |
| **17** | **Subtraction (1–30)** — Objects + Numerals | .0 Mastery, .1 Easier, .2 Remedial |
| **18** | **Ordering (Ascend/Descend)** — Arrange 4–5 numbers | .0 Mastery, .1 Easier, .2 (jars) |
| **19** | *(empty templates)* | .0, .1 |
| **20** | **Skip Counting (2s & 3s)** — Fill missing | .0 Mastery, .1 (frog jump), .2 Remedial |
| **21** | **Comparison (>, <, =)** — Numbers + objects | .0 Mastery, .1 Easier, .2 Remedial |
| **22** | **Ordering 2–3 numbers** — Ascend + Descend | .0 (example), .1 (3 nums), .2 (2 nums) |
| **23** | **Review Assessment 3** — Cumulative review of L12–22 | .0 Mastery, .1 Easier, .2 Remedial |
| **24** | **Place Value (51–100)** — Numbers, counting, sequencing | .0, .1, .2 |
| **25** | **Carry Addition (2-digit)** — With regrouping | .0, .1, .2 |
| **26** | **Borrow Subtraction (2-digit)** — With regrouping | .0, .1, .2 |
| **27** | *(skipped — no search queries)* | — |
| **28** | **Ordering (Ascend/Descend to 100)** | .0, .1, .2 |
| **29** | **Tally Marks** — Count, draw, interpret | .0, .1, .2 |
| **30** | **Time (Analog Clock)** — Hour & half-hour | .0, .1, .2 |
| **31** | **Ordinal Positions** — 1st to 10th | .0, .1, .2 |
| **32** | **Multiplication (Repeated Addition)** — Equal groups, arrays | .0, .1, .2 |

## Pipeline

```
Config (interactive prompts)
    ↓
Scrape DuckDuckGo + Wikimedia Commons (QUERY-based)
   OR
Copy images from source levels (for REVIEW assessments)
    ↓
Simplify to B&W line art (OpenCV adaptive threshold + morph cleanup)
    ↓
Deduplicate (perceptual hashing via imagehash)
    ↓
Generate HTML table (Q No. | Illustration | Question) → Google Docs ready
    ↓
Generate DOCX (Cambria font, 3-column tables, images embedded)
    ↓
Generate question text via LLM (Ollama Gemma2:12b / Gemini API)
    ↓
fln_questions.json — per-image: question_text, level, topic, difficulty,
                      skill_codes, ncf_alignment, question_type, blooms_level
```

## File Structure

```
FLN_Formatted_Document_2/
├── fln_specific_level_populator.ipynb   ← MAIN NOTEBOOK (17 cells)
│   • Install deps (DDGS, Pillow, opencv, imagehash)
│   • Interactive config
│   • Search queries per level
│   • Image download utilities + dedup
│   • B&W stickfigure simplification (simplify_image / simplify_all_images)
│   • DDG scraper + Wiki scraper
│   • Main loop (scrape OR copy for review levels, then simplify)
│   • HTML table generator (prefers _simplified.png)
│   • Post-process: simplify existing images
│   • LLM question gen: Ollama (Gemma 12B) or Gemini API
│   • JSON validator + aggregator
│
└── content/fln_output/
    ├── fln_tables.html           ← HTML tables (252 image rows + 60 Level 23 text)
    ├── fln_tables.docx           ← DOCX with embedded images (25 MB)
    ├── fln_questions.json        ← LLM-generated question data
    └── pinterest_images/
        └── Level_* /
            └── *.*_Mastery|Easier_Remediation|Further_Remediation/
                ├── 001.jpg          ← original scraped image
                ├── 001_simplified.png ← B&W stickfigure version
                └── ...
```

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Image sources | DuckDuckGo + Wikimedia Commons only (Bing removed — inappropriate results) |
| Image style | B&W line art via OpenCV adaptive threshold + morphological cleanup |
| Output font | Cambria (3-column table: Q No. | Illustration | Question) |
| No colors | Clean B&W tables — no colored headers for print-friendliness |
| Review assessments | Copy from source sub-dirs (not scrape) |
| Config | Interactive terminal prompts (not hardcoded) |
| LLM for questions | Ollama (gemma2:12b) or Google Gemini API |
| Question output | JSON with: question_text, level, topic, difficulty, skill_codes, ncf_alignment, question_type, blooms_level, expected_answer |

## Running on Colab

1. Upload notebook to [Google Colab](https://colab.research.google.com)
2. **Runtime → Run all**
3. Answer prompts in the terminal:
   - BASE path (default: `/content/fln_output`)
   - Images per sub-level (default: 12)
   - Level numbers to scrape
   - Review assessment ranges
   - LLM provider (ollama/gemini)
4. Download outputs:
   ```python
   from google.colab import files
   files.download("/content/fln_output/fln_tables.html")
   files.download("/content/fln_output/fln_questions.json")
   ```

## Quick Reference — Level Topics & Queries

For each level, the notebook uses 10 search queries tailored to the topic, with difficulty modifier (`practice` / `easy` / `beginner`) appended per sub-level.

| Level | Topic | Example Query |
|-------|-------|--------------|
| 24 | Place Value 51–100 | `numbers 51-100 worksheet` |
| 25 | Carry Addition | `addition with regrouping worksheet` |
| 26 | Borrow Subtraction | `subtraction with borrowing grade 2` |
| 28 | Ordering | `ascending descending order worksheet` |
| 29 | Tally Marks | `count tally marks worksheet` |
| 30 | Analog Clock | `tell time worksheet` |
| 31 | Ordinals | `ordinal numbers worksheet` |
| 32 | Repeated Addition | `equal groups worksheet` |

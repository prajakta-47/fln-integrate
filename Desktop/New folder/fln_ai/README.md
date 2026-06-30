# FLN AI — FLN Educational Knowledge Extraction Engine

Phase 1 of the FLN project: Convert heterogeneous worksheets into a standardized Question Knowledge Base.

## Package Structure

```
fln_ai/
├── __init__.py          # Package init, version 1.0.0
├── config.py            # Central configuration (paths, model params, thresholds)
├── database/            # Question repository and storage
│   └── repository.py    # QuestionRepository — persist/load questions with confidence
├── dataset/             # Dataset management
│   └── manager.py       # DatasetManager — ingest, deduplicate, stage processed files
├── difficulty/          # Difficulty classification
│   └── classifier.py    # DifficultyClassifier — score questions 0-100
├── gemma/               # Gemma 4 26B model integration
│   ├── loader.py        # GemmaLoader — model download and loading
│   └── analyzer.py      # GemmaAnalyzer — inference with prompt loading
├── layout/              # Document layout detection
│   ├── detector.py      # LayoutDetector — DocLayout-YOLO or heuristic fallback
│   └── document_parser.py # DocumentParser — full page parsing
├── normalization/       # Concept/Term normalization
│   └── engine.py        # NormalizationEngine — standardize question metadata
├── preprocessing/       # Image preprocessing
│   └── engine.py        # PreprocessingEngine — deskew, denoise, CLAHE, upscale
├── prompts/             # Prompt templates for Gemma (text files)
├── question_seg/        # Question segmentation
│   └── segmenter.py     # QuestionSegmenter — crop individual questions
├── scripts/             # Standalone pipelines and utilities
│   ├── run_pipeline.py  # Main pipeline orchestrator (FLN knowledge base)
│   ├── sidewise_processor.py # Sidewise worksheet analysis
│   └── human_review.py  # Human review workflow for low-confidence questions
└── validation/          # Output validation
    └── json_validator.py # JSONValidator — validate question records
```

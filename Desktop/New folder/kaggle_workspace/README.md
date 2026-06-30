# Kaggle Workspace

Contains the Kaggle notebook analysis script for running Gemma 4 26B on segmented question crops.

## Files

| File | Purpose |
|------|---------|
| `kaggle_analyzer.py` | `GemmaWorksheetAnalyzer` class — loads Gemma 4 26B via llama-cpp-python, analyzes pre-segmented question crops, and outputs structured JSON with 20-field question specifications. |

## Usage (in Kaggle notebook)

```python
from kaggle_analyzer import GemmaWorksheetAnalyzer
analyzer = GemmaWorksheetAnalyzer()
analyzer.load_gemma()
analyzer.analyze_all("workspace_results/all_questions_consolidated.json")
```

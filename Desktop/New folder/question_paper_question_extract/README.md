# Question Paper Question Extract

Extracts individual questions from worksheet images and analyzes them using Gemma 4 26B.

## Files

| File | Purpose |
|------|---------|
| `question_extractor.py` | `WorksheetExtractor` class — segments questions from worksheet images, analyzes each crop with Gemma, extracts question text and answer. |
| `question_paper_analyzer.py` | `QuestionPaperAnalyzer` class — detailed analysis extracting 20+ fields per question (type, structure, objects, difficulty, etc.) with multi-column layout support. |
| `build_colab_nb.py` | Builds a Colab notebook version of the analyzer. |
| `build_kaggle_nb.py` | Builds a Kaggle notebook version. |
| `*.ipynb` | Jupyter notebooks for Kaggle/Colab execution. |
| `*.jpg`, `*.json` | Test input files. |

## Usage

```bash
python question_extractor.py --input worksheet.jpg --output ./results
python question_paper_analyzer.py -i worksheet.jpg -o ./results
```

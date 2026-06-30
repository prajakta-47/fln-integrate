import json
import base64
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_HTML = Path(__file__).parent / "question_report.html"

def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_image_path(image_dir):
    folder_name = image_dir.name
    png = image_dir / f"{folder_name}.png"
    jpg = image_dir / f"{folder_name}.jpg"
    if png.exists():
        return png
    if jpg.exists():
        return jpg
    return None

def build_question_text(data):
    def safe(val):
        return str(val).strip() if val is not None else ""
    heading = safe(data.get("question_heading"))
    action = safe(data.get("student_action"))
    detected = safe(data.get("all_text_detected"))

    heading_clean = "" if heading in ("None visible", "", "None") else heading

    action_used = ""
    short_actions = {"circle", "match", "color", "colour", "count", "circle and draw"}
    if action and action.lower() not in short_actions:
        action_used = action
    elif action and action.lower() in short_actions:
        if detected:
            action_used = detected
        else:
            action_used = action.capitalize()
    elif detected:
        action_used = detected

    return heading_clean, action_used

def build_html():
    manifest = load_json(DATA_DIR / "batch_manifest.json")

    cards = []
    for entry in manifest["batch"]:
        filename = entry["file"]
        folder_name = filename.rsplit(".", 1)[0]
        image_dir = DATA_DIR / folder_name

        img_path = get_image_path(image_dir)
        json_path = image_dir / f"{folder_name}_result.json"

        if not img_path or not json_path.exists():
            continue

        data = load_json(json_path)
        img_b64 = img_to_base64(img_path)
        img_ext = img_path.suffix[1:]

        heading, instruction = build_question_text(data)

        cards.append(f"""
        <div class="card">
            <div class="card-header">
                <div class="header-left">
                    <span class="badge-type">{data.get('question_type', '')}</span>
                    <span class="badge-grade">{data.get('estimated_grade', '')}</span>
                </div>
                <div class="header-right">
                    <span class="badge-confidence">{data.get('confidence_score', '')}% confidence</span>
                </div>
            </div>
            <div class="card-body">
                <div class="image-section">
                    <img src="data:image/{img_ext};base64,{img_b64}" alt="{folder_name}">
                </div>
                <div class="question-section">
                    <div class="question-heading">{heading}</div>
                    <div class="question-instruction">{instruction}</div>
                </div>
            </div>
        </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Worksheet Question Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: #eef1f5;
    padding: 40px 24px;
    color: #1d1d1f;
}}

.page-header {{
    max-width: 1200px;
    margin: 0 auto 36px auto;
    text-align: center;
}}

.page-header h1 {{
    font-size: 28px;
    font-weight: 700;
    color: #1d1d1f;
    letter-spacing: -0.5px;
}}

.page-header .subtitle {{
    margin-top: 6px;
    font-size: 15px;
    color: #86868b;
}}

/* --- Card --- */
.card {{
    max-width: 1200px;
    margin: 0 auto 28px auto;
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
    overflow: hidden;
}}

/* --- Header --- */
.card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
    background: #f7f8fa;
    border-bottom: 1px solid #e8eaed;
}}

.header-left, .header-right {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.badge-type {{
    display: inline-block;
    background: #e8ecf4;
    color: #3a3f5c;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    letter-spacing: 0.3px;
}}

.badge-grade {{
    display: inline-block;
    background: #e6f0eb;
    color: #2d6a4f;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 20px;
}}

.badge-confidence {{
    font-size: 12px;
    color: #86868b;
    font-weight: 500;
}}

/* --- Body --- */
.card-body {{
    display: flex;
    gap: 28px;
    padding: 24px;
}}

.image-section {{
    flex: 0 0 48%;
    max-width: 48%;
    display: flex;
    align-items: flex-start;
}}

.image-section img {{
    width: 100%;
    height: auto;
    max-height: 520px;
    object-fit: contain;
    border-radius: 10px;
    border: 1px solid #e8eaed;
    background: #fafbfc;
}}

.question-section {{
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
}}

.question-heading {{
    font-size: 22px;
    font-weight: 700;
    color: #1d1d1f;
    line-height: 1.35;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 2px solid #e8eaed;
}}

.question-instruction {{
    font-size: 16px;
    line-height: 1.7;
    color: #3a3a3c;
    background: #f8f9fc;
    padding: 18px 22px;
    border-radius: 10px;
    border-left: 4px solid #5677e8;
}}

/* --- Empty state --- */
.question-heading:empty {{
    display: none;
}}

.question-heading:empty + .question-instruction {{
    border-top: none;
}}

@media (max-width: 820px) {{
    body {{ padding: 16px; }}
    .card-body {{
        flex-direction: column;
        padding: 16px;
    }}
    .image-section {{
        flex: none;
        max-width: 100%;
    }}
    .image-section img {{
        max-height: 380px;
    }}
}}

@media print {{
    body {{ background: #fff; padding: 0.5in; }}
    .card {{
        box-shadow: none;
        border: 1px solid #ddd;
        break-inside: avoid;
        page-break-inside: avoid;
        margin-bottom: 24px;
    }}
    .card-header {{ background: #f5f5f7; }}
}}
</style>
</head>
<body>
<div class="page-header">
    <h1>Worksheet Question Report</h1>
    <div class="subtitle">{len(cards)} worksheets</div>
</div>
{"".join(cards)}
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report generated: {OUTPUT_HTML}")
    print(f"Total questions: {len(cards)}")

if __name__ == "__main__":
    build_html()

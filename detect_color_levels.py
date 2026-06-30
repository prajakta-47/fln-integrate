#!/usr/bin/env python3
"""
FLN Color-Dependency Detector
Extracts images from DOCX files, analyzes which ones rely on color,
and generates an HTML report for quick manual review.
"""

import zipfile, os, io, re, json, base64
from pathlib import Path
from PIL import Image, ImageFilter
from collections import defaultdict
import numpy as np

# === CONFIG ===
DOCX_DIRS = [
    "/Users/pradipkumaracharya/Desktop/IIT Ropar On Site Internship/Assignments/FLN/FLN_Formatted_Document_2/docx_final",
    "/Users/pradipkumaracharya/Desktop/IIT Ropar On Site Internship/Assignments/FLN/FLN_Formatted_Document_2/docx_output",
]
OUTPUT_DIR = "/Users/pradipkumaracharya/Desktop/IIT Ropar On Site Internship/Assignments/FLN/color_report"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === ANALYSIS ===

def analyze_image(img_data):
    """Return dict with color dependency metrics."""
    try:
        img = Image.open(io.BytesIO(img_data))
        if img.mode != "RGB":
            img = img.convert("RGB")

        arr = np.array(img, dtype=np.float32)
        h, w = arr.shape[:2]

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # 1. Color saturation ratio
        sat = np.abs(r - g) + np.abs(g - b) + np.abs(b - r)
        color_ratio = float((sat > 40).mean())

        # 2. If >80% of image is one color (e.g. white bg with thin lines), still check content
        gray = np.mean(arr, axis=2)
        gray_img = Image.fromarray(gray.astype("uint8"))
        gray_edges = np.array(gray_img.filter(ImageFilter.FIND_EDGES))

        # Edge overlap across R channel
        r_img = Image.fromarray(r.astype("uint8"))
        r_edges = np.array(r_img.filter(ImageFilter.FIND_EDGES))

        gray_flat = gray_edges.flatten().astype(float)
        r_flat = r_edges.flatten().astype(float)
        if gray_flat.std() > 0 and r_flat.std() > 0:
            shape_corr = float(np.corrcoef(gray_flat, r_flat)[0, 1])
        else:
            shape_corr = 1.0

        # 3. Count distinct color clusters
        # Simple check: number of distinct hue bins in non-white pixels
        mask = sat > 20
        if mask.sum() > 1000:
            hues = []
            for i in range(h):
                for j in range(w):
                    if mask[i, j]:
                        rr, gg, bb = r[i, j], g[i, j], b[i, j]
                        if rr + gg + bb > 30:
                            # Simplified hue
                            if rr > gg and rr > bb:
                                hues.append("R")
                            elif gg > rr and gg > bb:
                                hues.append("G")
                            elif bb > rr and bb > gg:
                                hues.append("B")
                            elif rr > bb and gg > bb:
                                hues.append("Y")
                            else:
                                hues.append("O")
            distinct_hues = len(set(hues)) if hues else 0
        else:
            distinct_hues = 0

        # Flag: high color ratio + same shapes across channels
        flagged = color_ratio > 0.08

        return {
            "color_ratio": round(color_ratio, 3),
            "shape_corr": round(shape_corr, 3),
            "distinct_hues": distinct_hues,
            "flagged": flagged,
        }
    except Exception as e:
        return None


def extract_images_from_docx(path):
    """Extract all images from a .docx file. Returns list of (filename, bytes)."""
    images = []
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.startswith("word/media/"):
                    data = z.read(name)
                    images.append((os.path.basename(name), data))
    except Exception as e:
        print(f"  [WARN] Could not read {path}: {e}")
    return images


def image_to_base64(data, fmt="PNG"):
    """Convert image bytes to base64 data URL."""
    b64 = base64.b64encode(data).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def html_color(value, threshold=0.08):
    return "#d32f2f" if value > threshold else "#2e7d32"


# === MAIN ===

results = []  # list of dicts per image

for docx_dir in DOCX_DIRS:
    if not os.path.exists(docx_dir):
        continue
    for fname in sorted(os.listdir(docx_dir)):
        if not fname.endswith(".docx"):
            continue
        m = re.match(r"Level_(\d+)", fname)
        level = int(m.group(1)) if m else 0

        path = os.path.join(docx_dir, fname)
        images = extract_images_from_docx(path)

        for img_name, img_data in images:
            analysis = analyze_image(img_data)
            results.append({
                "level": level,
                "doc": fname,
                "image": img_name,
                "size": f"{analysis.get('size', '?')}" if analysis else "?",
                "color_ratio": analysis["color_ratio"] if analysis else 0,
                "shape_corr": analysis["shape_corr"] if analysis else 0,
                "distinct_hues": analysis["distinct_hues"] if analysis else 0,
                "flagged": analysis["flagged"] if analysis else False,
                "img_b64": image_to_base64(img_data),
            })

# === GENERATE HTML REPORT ===

level_summary = defaultdict(lambda: {"total": 0, "color": 0, "gray": 0})
for r in results:
    ls = level_summary[r["level"]]
    ls["total"] += 1
    if r["flagged"]:
        ls["color"] += 1
    else:
        ls["gray"] += 1

color_levels = [lvl for lvl, s in level_summary.items() if s["color"] > 0]

html_rows = ""
flagged_rows = ""
for r in results:
    color = html_color(r["color_ratio"])
    row = f"""<tr>
  <td>L{r["level"]}</td>
  <td title="{r["doc"]}">{r["doc"][:40]}</td>
  <td>{r["image"]}</td>
  <td>{r["size"]}</td>
  <td style="color:{color};font-weight:bold">{r["color_ratio"]*100:.1f}%</td>
  <td>{r["shape_corr"]}</td>
  <td>{r["distinct_hues"]}</td>
  <td>{"<span style='color:#d32f2f'>YES</span>" if r["flagged"] else "<span style='color:#2e7d32'>no</span>"}</td>
  <td><img src="{r["img_b64"]}" style="max-width:180px;max-height:120px;border:1px solid #ddd"></td>
</tr>"""
    html_rows += row + "\n"
    if r["flagged"]:
        flagged_rows += row + "\n"

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FLN Color Dependency Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
h1, h2, h3 {{ color: #333; }}
table {{ border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
th {{ background: #1976d2; color: #fff; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
tr:hover {{ background: #e3f2fd; }}
.summary-box {{ background: #fff; border-radius: 8px; padding: 16px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
.badge-red {{ background: #ffcdd2; color: #c62828; }}
.badge-green {{ background: #c8e6c9; color: #2e7d32; }}
</style>
</head>
<body>
<h1>🎨 FLN Color-Dependency Detector</h1>

<div class="summary-box">
<h2>Summary</h2>
<p>Scanned <strong>{len(results)}</strong> images across <strong>{len(level_summary)}</strong> levels.</p>
<p>
<strong>Levels with color-reliant images:</strong>
{', '.join(f'L{lvl} ({s["color"]}/{s["total"]})' for lvl, s in sorted(level_summary.items()) if s["color"] > 0) if color_levels else "None detected"}
</p>

<h3>Per-Level Breakdown</h3>
<table>
<tr><th>Level</th><th>Total Img</th><th>🎨 Color</th><th>⬜ B&W</th><th>Status</th></tr>
"""
for lvl in sorted(level_summary.keys()):
    s = level_summary[lvl]
    status_class = "badge-red" if s["color"] > 0 else "badge-green"
    status_text = "REVIEW" if s["color"] > 0 else "OK"
    html += f"""<tr>
  <td><strong>L{lvl}</strong></td>
  <td>{s["total"]}</td>
  <td>{s["color"]}</td>
  <td>{s["gray"]}</td>
  <td><span class="badge {status_class}">{status_text}</span></td>
</tr>
"""
html += """</table>
</div>"""

if flagged_rows:
    html += f"""
<div class="summary-box">
<h2>🎨 Color-Reliant Images (flag for review)</h2>
<p class="badge badge-red">{sum(1 for r in results if r["flagged"])} images flagged</p>
<table>
<tr><th>Level</th><th>Doc</th><th>Image</th><th>Size</th><th>Color %</th><th>Shape Corr</th><th>Hues</th><th>Flagged</th><th>Preview</th></tr>
{flagged_rows}
</table>
</div>"""

html += f"""
<div class="summary-box">
<h2>📋 All Images</h2>
<table>
<tr><th>Level</th><th>Doc</th><th>Image</th><th>Size</th><th>Color %</th><th>Shape Corr</th><th>Hues</th><th>Flagged</th><th>Preview</th></tr>
{html_rows}
</table>
</div>

<p style="color:#888;font-size:12px">Generated by detect_color_levels.py — {os.path.basename(OUTPUT_DIR)}</p>
</body>
</html>"""

report_path = os.path.join(OUTPUT_DIR, "color_report.html")
with open(report_path, "w") as f:
    f.write(html)

# === ALSO SAVE CSV ===
csv_path = os.path.join(OUTPUT_DIR, "color_report.csv")
with open(csv_path, "w") as f:
    f.write("level,doc,image,size,color_ratio,shape_corr,hues,flagged\n")
    for r in results:
        f.write(f'{r["level"]},{r["doc"]},{r["image"]},{r["size"]},{r["color_ratio"]},{r["shape_corr"]},{r["distinct_hues"]},{r["flagged"]}\n')

print(f"Report saved: {report_path}")
print(f"CSV saved: {csv_path}")
print(f"\nSummary: {len(results)} images, {sum(1 for r in results if r['flagged'])} color-reliant, {len(color_levels)} affected levels")
print(f"Affected levels: {color_levels}")
print(f"Open the HTML report in a browser to review images side-by-side.")

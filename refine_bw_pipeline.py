#!/usr/bin/env python3
"""
Refine B&W stickfigure pipeline:
1. Improved adaptive threshold algorithm (handles more edge cases)
2. Regenerate HTML table preferring simplified images
3. Quality check: filesize comparison (tiny = over-thresholded)
"""
import os, re
from pathlib import Path
from collections import OrderedDict, defaultdict
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np

BASE = Path("/Users/pradipkumaracharya/Desktop/IIT Ropar On Site Internship/Assignments/FLN/FLN_Formatted_Document_2")
PINTEREST_DIR = BASE / "pinterest_images(23-32)"
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
SIM_SUFFIX = "_simplified.png"

# ==============================================================
# IMPROVED STICKFIGURE CONVERSION
# ==============================================================

def simplify_stickfigure_v2(img_path, overwrite=True):
    """Improved B&W stickfigure conversion with adaptive block sizing."""
    out = img_path.parent / f"{img_path.stem}{SIM_SUFFIX}"
    if out.exists() and not overwrite:
        return out
    try:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        
        # Step 1: Grayscale with enhanced contrast
        gray = img.convert("L")
        enh = ImageEnhance.Contrast(gray).enhance(1.8)
        sharp = enh.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
        
        arr = np.array(sharp, dtype=np.float32)
        
        # Step 2: Adaptive block size based on image dimensions
        block = max(15, min(61, min(w, h) // 20))
        if block % 2 == 0:
            block += 1
        
        blur = np.array(sharp.filter(ImageFilter.BoxBlur(block))).astype(np.float32)
        
        # Step 3: Adaptive threshold — use median-based offset
        median_val = np.median(arr)
        threshold_offset = max(15, min(40, median_val * 0.12))
        binary = np.where(arr < (blur - threshold_offset), 0, 255).astype(np.uint8)
        
        # Step 4: Morphological cleanup
        result = Image.fromarray(binary, mode="L")
        
        # Remove speckles (erode then dilate)
        result = result.filter(ImageFilter.MinFilter(3))
        result = result.filter(ImageFilter.MaxFilter(3))
        
        # Thin line recovery: dilate slightly to thicken faint lines
        result = result.filter(ImageFilter.MaxFilter(3))
        
        result.save(out, "PNG")
        return out
    except Exception as e:
        print(f"  ERROR: {img_path.name} -> {e}")
        return None


def quality_check(img_path, sim_path):
    """Quick quality check: report if simplified image is too small (over-thresholded)."""
    try:
        orig_size = img_path.stat().st_size
        sim_size = sim_path.stat().st_size
        ratio = sim_size / max(orig_size, 1)
        # If simplified is < 5% of original size, likely over-thresholded (too much removed)
        return {"orig_bytes": orig_size, "sim_bytes": sim_size, "ratio": round(ratio, 3), "tiny": ratio < 0.05}
    except Exception:
        return {"ratio": 0, "tiny": False}


# ==============================================================
# REGENERATE ALL SIMPLIFIED IMAGES WITH V2
# ==============================================================

print("=== Step 1: Regenerate all simplified images (v2 algorithm) ===\n")

all_images = []
for ldir in sorted(PINTEREST_DIR.iterdir()):
    if not ldir.is_dir(): continue
    for sdir in sorted(ldir.iterdir()):
        if not sdir.is_dir(): continue
        for f in sorted(sdir.iterdir()):
            if f.suffix.lower() not in VALID_EXTS or f.name.endswith(SIM_SUFFIX) or "_gray" in f.name:
                continue
            all_images.append(f)

print(f"Processing {len(all_images)} images...")

quality_issues = []
for i, fpath in enumerate(all_images):
    if (i+1) % 20 == 0:
        print(f"  {i+1}/{len(all_images)}...")
    sim_path = simplify_stickfigure_v2(fpath, overwrite=True)
    if sim_path:
        qc = quality_check(fpath, sim_path)
        if qc["tiny"]:
            quality_issues.append((fpath, qc))

if quality_issues:
    print(f"\n⚠️  {len(quality_issues)} images may be over-thresholded (tiny output):")
    for p, q in quality_issues[:10]:
        print(f"    {p.name} — orig {q['orig_bytes']}B → bw {q['sim_bytes']}B ({q['ratio']*100:.1f}%)")
else:
    print("\n✅ All images pass quality check")

# ==============================================================
# REGENERATE HTML TABLE (preferring simplified images)
# ==============================================================

print("\n=== Step 2: Regenerate HTML table with simplified images ===")

def get_subdirs(dir_path):
    subdirs = sorted([d for d in dir_path.iterdir() if d.is_dir()])
    result = []
    for d in subdirs:
        if d.name.startswith("_"):
            result.extend(sorted([s for s in d.iterdir() if s.is_dir()]))
        else:
            result.append(d)
    return result

rows = []
for level_dir in sorted(PINTEREST_DIR.iterdir()):
    if not level_dir.is_dir():
        continue
    m = re.search(r'Level_(\d+)', level_dir.name)
    level_num = m.group(1) if m else "?"
    
    for sub_dir in get_subdirs(level_dir):
        parts = sub_dir.name.split("_", 1)
        sub_code = parts[0] if parts else ""
        
        classify = "mastery" if ".0" in sub_code else ("remediation_easier" if ".1" in sub_code else "remediation_further")
        
        # Skip _gray files and simplified root
        all_imgs = sorted([f for f in sub_dir.iterdir() 
                          if f.suffix.lower() in VALID_EXTS and "_gray" not in f.name])
        sim_imgs = [f for f in all_imgs if f.name.endswith("_simplified.png")]
        use_imgs = sim_imgs if sim_imgs else [f for f in all_imgs if not f.name.endswith("_simplified.png")]
        
        for i, img_path in enumerate(use_imgs, 1):
            rows.append({
                "q_no": i,
                "illustration": str(img_path.relative_to(BASE)),
                "level": level_num,
                "sub_level": sub_code,
                "classification": classify,
                "is_simplified": img_path.name.endswith("_simplified.png")
            })

levels = OrderedDict()
for r in rows:
    key = (r["level"], r["sub_level"], r["classification"])
    levels.setdefault(key, []).append(r)

html_parts = ['<html><head><meta charset="utf-8">']
html_parts.append('<style>')
html_parts.append('body { font-family: "Cambria", serif; font-size: 11pt; margin: 20px; }')
html_parts.append('h2 { font-family: "Cambria", serif; color: #1a5276; }')
html_parts.append('table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }')
html_parts.append('th, td { border: 1px solid #999; padding: 6px 10px; vertical-align: middle; font-family: "Cambria", serif; }')
html_parts.append('th { background-color: #d4e6f1; font-weight: bold; }')
html_parts.append('img { max-width: 120px; max-height: 120px; }')
html_parts.append('.bw-badge { font-size: 9px; color: #666; }')
html_parts.append('</style></head><body>')

for key, group in levels.items():
    level_num, sub_code, classify = key
    label = classify.replace("_", " ").title()
    html_parts.append(f'<h2>Level {level_num} — Sub-level {sub_code} ({label})</h2>')
    html_parts.append('<table>')
    html_parts.append('<tr><th>Q No.</th><th>Illustration</th><th>Question</th></tr>')
    for r in group:
        img_abs = str(BASE / r["illustration"])
        badge = ' <span class="bw-badge">(B&W)</span>' if r["is_simplified"] else ' <span class="bw-badge" style="color:#c62828">(color)</span>'
        html_parts.append(
            f'<tr><td>{r["q_no"]}</td>'
            f'<td><img src="file://{img_abs}">{badge}</td>'
            f'<td></td></tr>'
        )
    html_parts.append('</table>')

html_parts.append('</body></html>')

out_path = BASE / "fln_tables.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(html_parts))

# Count: how many images use simplified vs color
total_rows = len(rows)
sim_count = sum(1 for r in rows if r["is_simplified"])
color_count = total_rows - sim_count

print(f"\n=== SUMMARY ===")
print(f"Total rows in table: {total_rows}")
print(f"Using B&W simplified: {sim_count} ({sim_count/total_rows*100:.1f}%)")
print(f"Using color originals: {color_count} ({color_count/total_rows*100:.1f}%)")
print(f"No simplified available: {color_count} (fallback to color)")
print(f"\nOutput: {out_path}")
print(f"Open in browser, Ctrl+A → Ctrl+C → paste into Google Docs or Word")

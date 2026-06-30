#!/usr/bin/env python3
"""
FLN B&W Filter — flags images that become incomprehensible in grayscale.
Does NOT post-process. Just tells you what needs manual replacement.
"""
import os, csv
from pathlib import Path
from collections import defaultdict
from PIL import Image
import numpy as np

BASE = Path("/Users/pradipkumaracharya/Desktop/IIT Ropar On Site Internship/Assignments/FLN/FLN_Formatted_Document_2")
PINTEREST_DIR = BASE / "pinterest_images(23-32)"
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
OUTPUT = BASE / "bw_filter_report.html"

def check_image(img_path):
    """Returns True if image is OK in grayscale, False if it needs replacement."""
    try:
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((128, 128))
        arr = np.array(img, dtype=np.float32)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]

        # Metric 1: Color saturation — how much of the image uses actual color
        sat = np.abs(r - g) + np.abs(g - b) + np.abs(b - r)
        color_pct = float((sat > 40).mean()) * 100

        # Metric 2: Channel divergence — do R/G/B channels carry different info?
        gray = np.mean(arr, axis=2)
        def corr(a, b):
            if a.std() == 0 or b.std() == 0: return 1.0
            return float(np.corrcoef(a.flatten(), b.flatten())[0, 1])
        min_corr = min(corr(r, g), corr(r, b), corr(g, b))
        ch_div = round(1.0 - min_corr, 3)

        # Metric 3: Distinct color groups
        mask = sat > 40
        hues = set()
        if mask.sum() > 50:
            for i in range(0, arr.shape[0], 3):
                for j in range(0, arr.shape[1], 3):
                    if mask[i, j]:
                        rr, gg, bb = r[i,j], g[i,j], b[i,j]
                        if rr+gg+bb > 30:
                            if rr > gg and rr > bb: hues.add("R")
                            elif gg > rr and gg > bb: hues.add("G")
                            elif bb > rr and bb > gg: hues.add("B")
                            elif rr > bb and gg > bb: hues.add("Y")
                            elif rr > gg and bb > gg: hues.add("C")
                            else: hues.add("M")

        # Decision: image needs replacement if:
        # - High color saturation + channel divergence (color IS the information)
        # - Or many distinct hues (rainbow chart, colored groups)
        needs_replacement = (color_pct > 20 and ch_div > 0.15) or (len(hues) >= 4)

        reasons = []
        if color_pct > 20: reasons.append(f"Color: {color_pct:.0f}% pixels colored")
        if ch_div > 0.15: reasons.append(f"Channels differ: {ch_div:.2f}")
        if len(hues) >= 4: reasons.append(f"{len(hues)} distinct color groups")
        if ch_div > 0.25: reasons.append("HIGH: color carries critical info")

        return {
            "needs_replacement": needs_replacement,
            "color_pct": round(color_pct, 1),
            "ch_div": ch_div,
            "hues": len(hues),
            "reason": "; ".join(reasons) if reasons else "OK in grayscale"
        }
    except Exception as e:
        return {"needs_replacement": True, "color_pct": 0, "ch_div": 0, "hues": 0, "reason": f"Error: {e}"}


# === SCAN ===
import re
results = []

for ldir in sorted(PINTEREST_DIR.iterdir()):
    if not ldir.is_dir(): continue
    m = re.search(r'Level_(\d+)', ldir.name)
    lvl = int(m.group(1)) if m else 0
    for sdir in sorted(ldir.iterdir()):
        if not sdir.is_dir(): continue
        sc = sdir.name.split("_")[0] if "_" in sdir.name else sdir.name
        for f in sorted(sdir.iterdir()):
            if f.suffix.lower() not in VALID_EXTS or "_simplified" in f.name or "_gray" in f.name:
                continue
            check = check_image(f)
            results.append({
                "level": lvl, "sub": sc, "name": f.name,
                "path": str(f.relative_to(BASE)),
                "abs": str(f),
                "check": check
            })

# === GENERATE REPORT ===
total = len(results)
bad = [r for r in results if r["check"]["needs_replacement"]]

level_stats = defaultdict(lambda: {"total": 0, "bad": 0})
for r in results:
    s = level_stats[r["level"]]
    s["total"] += 1
    if r["check"]["needs_replacement"]: s["bad"] += 1

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>FLN B&W Filter Report</title>
<style>
body{{font-family:-apple-system,sans-serif;margin:20px;background:#f5f5f5}}
h1,h2,h3{{color:#1a1a2e}}
table{{border-collapse:collapse;margin:16px 0;font-size:12px;width:100%}}
th,td{{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:middle}}
th{{background:#1a5276;color:#fff;position:sticky;top:0}}
tr:nth-child(even){{background:#f9f9f9}}
tr:hover{{background:#e3f2fd}}
.box{{background:#fff;border-radius:8px;padding:16px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,0.2)}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:bold}}
.badge-red{{background:#ffcdd2;color:#c62828}}
.badge-green{{background:#c8e6c9;color:#2e7d32}}
.badge-amber{{background:#ffe0b2;color:#e65100}}
img{{max-width:120px;max-height:100px;border:1px solid #ddd;border-radius:3px}}
.details{{font-size:10px;color:#666;max-width:200px}}
</style></head><body>
<div class="box">
<h1>FLN B&W Filter Report</h1>
<p>Scanned <strong>{total}</strong> images across <strong>{len(level_stats)}</strong> levels.</p>
<p><span class="badge {'badge-red' if len(bad) > 0 else 'badge-green'}">{len(bad)} images ({len(bad)/total*100:.1f}%) need manual replacement — incomprehensible in B&W</span></p>
<p style="font-size:12px;color:#888">This is a FILTER only. No images were modified. Open the original images to review.</p>
</div>"""

# Per-level
html += '<div class="box"><h2>Per-Level</h2><table><tr><th>Level</th><th>Total</th><th>Replace</th><th>Status</th></tr>'
for lvl in sorted(level_stats.keys()):
    s = level_stats[lvl]
    cls = "badge-red" if s["bad"] > 0 else "badge-green"
    st = f"Fix {s['bad']} images" if s['bad'] > 0 else "OK"
    html += f'<tr><td>L{lvl}</td><td>{s["total"]}</td><td>{s["bad"]}</td><td><span class="badge {cls}">{st}</span></td></tr>'
html += '</table></div>'

# Bad images
if bad:
    html += f'<div class="box"><h2>Images Needing Replacement ({len(bad)})</h2><table><tr><th>Level</th><th>Image</th><th>Original</th><th>Issue</th></tr>'
    for r in sorted(bad, key=lambda x: (x["level"], x["sub"], x["name"])):
        c = r["check"]
        severity = "badge-red" if c["ch_div"] > 0.25 else "badge-amber"
        html += f"""<tr>
<td>L{r["level"]} {r["sub"]}</td>
<td><small>{r["name"]}</small></td>
<td><img src="file://{r['abs']}"></td>
<td><span class="badge {severity}">REPLACE</span><div class="details">{c["reason"]}</div></td>
</tr>"""
    html += '</table></div>'

# All images
html += f'<div class="box"><h2>All Images ({total})</h2><table><tr><th>Level</th><th>Image</th><th>Status</th></tr>'
for r in sorted(results, key=lambda x: (x["level"], x["sub"], x["name"])):
    badge = '<span class="badge badge-red">REPLACE</span>' if r["check"]["needs_replacement"] else '<span class="badge badge-green">OK</span>'
    html += f'<tr><td>L{r["level"]} {r["sub"]}</td><td><small>{r["name"]}</small></td><td>{badge}</td></tr>'
html += '</table></div>'
html += '</body></html>'

with open(OUTPUT, "w") as f:
    f.write(html)

# CSV
csv_path = OUTPUT.parent / "bw_filter_report.csv"
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["level", "sub_level", "image", "needs_replacement", "color_pct", "ch_div", "hues", "reason"])
    for r in results:
        c = r["check"]
        w.writerow([r["level"], r["sub"], r["name"], c["needs_replacement"], c["color_pct"], c["ch_div"], c["hues"], c["reason"]])

print(f"Report: {OUTPUT}")
print(f"CSV:    {csv_path}")
print(f"Total:  {total}")
print(f"Replace: {len(bad)} ({len(bad)/total*100:.1f}%)")
for lvl in sorted(level_stats.keys()):
    s = level_stats[lvl]
    if s["bad"]:
        print(f"  L{lvl}: {s['bad']}/{s['total']} need replacement")

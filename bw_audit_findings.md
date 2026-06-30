# B&W Readability Audit — Findings Report (30-06-2026)

## Pipeline Issue: Current Simplification is Just Grayscale

The `simplify_image` function in `fln_specific_level_populator.ipynb:321` was doing `cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)` — a naive grayscale conversion. It does **not** produce stickfigure-style line art as described in the pipeline docs.

**Fix applied:** Replaced with adaptive threshold + morphological cleanup that produces proper B&W line art. Output is binary (pure black on white), print-friendly, and preserves line detail much better than grayscale.

---

## Levels 1–22: Color Dependency Analysis

| Level | Topic | Status | Notes |
|-------|-------|--------|-------|
| 1 | Quantity Comparison | ✅ B&W Safe | Visual quantity matching, no color |
| 2 | Odd One Out | ⚠️ **COLOR-DEPENDENT** | "colour" listed as classification attribute in spec |
| 3 | Matching + Tracing | ✅ B&W Safe | Shape matching, line tracing |
| 4 | Numbers 1–10 | ✅ B&W Safe | Finger gestures, numerals |
| 5 | Finger Gesture Counting | ✅ B&W Safe | Quantity-to-gesture matching |
| 6 | After/Between/Before | ✅ B&W Safe | Pure numeral sequencing |
| 7 | Addition (objects) | ✅ B&W Safe | Object-group counting |
| 8 | Subtraction (objects) | ✅ B&W Safe | Object-group subtraction |
| 9 | Pattern Recognition | ✅ B&W Safe | Shape/symbol patterns, tracing |
| 10 | Comparison (Numeral) | ✅ B&W Safe | > < = with numerals |
| 11 | Review Assessment | ✅ B&W Safe | Review of 1–10 |
| 12 | Tens and Ones | ⚠️ **POTENTIALLY PROBLEMATIC** | Uses 🟦=10, 🟨=1 colored blocks in examples |
| 13 | Numbers 11–30 | ✅ B&W Safe | Numerals, number names |
| 14 | Counting + Trace | ✅ B&W Safe | Object-number matching |
| 15 | Mixed (After/Before) | ✅ B&W Safe | Numerals only |
| 16 | Addition (1–30) | ✅ B&W Safe | Objects + numerals |
| 17 | Subtraction (1–30) | ✅ B&W Safe | Objects + numerals |
| 18 | Ordering | ✅ B&W Safe | Ascending/descending numerals |
| 19 | Numbering 31–50 | ✅ B&W Safe | Numerals, number names |
| 20 | Skip Counting 2s/3s | ✅ B&W Safe | Number patterns, frog-jump |
| 21 | Comparison (1–50) | ✅ B&W Safe | > < = with numerals |
| 22 | Ordering | ✅ B&W Safe | Ascending/descending |

### Specific Concern: Level 2 — Odd One Out
The spec (`Level 2/Level 2_ Odd One Out.md:11`) says children classify objects by "shape, size, **colour**, quantity or category." If worksheets include color-based odd-one-out tasks (e.g., 3 red apples + 1 green apple), the B&W version is unsolvable.

**Fix:** Either remove "colour" from the classification attributes, or ensure every color distinction has a secondary distinguishing cue (pattern/shape/texture).

### Specific Concern: Level 12 — Tens and Ones
The example in `12.0.md:22-27` uses colored emoji blocks: `🟦 = 10, 🟨 = 1`. These are indistinguishable in grayscale/B&W. The description does mention alternative representations (bundles, sticks, beads) that work in B&W.

**Fix:** Replace colored blocks with shape-differentiated symbols (e.g., ◼️ outlined square = 10, ● small circle = 1) or use bundle-of-sticks imagery.

---

## Levels 23–32: Automated Scan Results

153 images scanned across 8 levels. **61 flagged (39.9%)** for B&W readability issues.

| Level | Topic | Total | Flagged | Flag Rate |
|-------|-------|-------|---------|-----------|
| 23 | Review Assessment 3 | 13 | 3 | 23% |
| 25 | Carry Addition | 29 | 11 | 38% |
| 26 | Borrow Subtraction | 14 | 8 | 57% |
| 27 | Comparison (Up to 100) | 29 | 6 | 21% |
| 29 | Tally Marks | 21 | 12 | 57% |
| 30 | Analog Clock | 22 | 7 | 32% |
| 31 | Ordinal Positions | 20 | 12 | 60% |
| 32 | Multiplication (Repeated Add) | 5 | 2 | 40% |

### Why These Images Are Flagged

The main causes for flagging across levels 23–32:

1. **High color saturation (>15% colored pixels):** Images downloaded from web worksheets often use colorful decorations, colored borders, colored text (red numbers, blue instructions). These lose meaning when the color is the differentiator.

2. **Channel divergence (>0.15):** When R/G/B channels carry different information (e.g., red apples vs green apples in an addition problem), the B&W version conflates them into the same gray.

3. **Multiple distinct hue groups (≥3):** Worksheets using many colors (e.g., rainbow number charts, multi-colored tally charts) become flat gray blobs.

4. **Detail loss (>50%):** Some images are low-contrast illustrations where lines nearly disappear during thresholding. The stickfigure conversion recovers most of this, but some delicate-faint-line images lose detail.

### Key Problematic Image Categories Found in Scraped Data:

- **Color-coded place value blocks** (tens in blue, ones in green) — indistinguishable in B&W
- **Colored comparison arrows/symbols** (red > blue <) — lose meaning when gray
- **Rainbow-colored number charts** — decorative color, not information-critical
- **Tally charts with colored data bars** — bars become indistinguishable grays
- **Ordinal position images with colored objects** (1st=red, 2nd=blue, 3rd=green)
- **Analog clocks with colored hands** (red second hand, blue minute hand)
- **Carry addition with colored carry-overs** (red "1" written above column)
- **Addition/subtraction with colored object groups** (red apples + green apples)

---

## Report File Generated

Open in browser: `bw_readability_report.html`

This report shows every image with:
- Original (full color)
- Grayscale (simple L-mode conversion)
- Stickfigure (adaptive threshold — the new improved version)
- Flag status and metrics

Also generated: `_simplified.png` files alongside each original image in `pinterest_images(23-32)/`.

---

## Recommendations

1. **Update all scraped images with new stickfigure conversion** — re-run the pipeline with the improved `simplify_image()` on all levels.
2. **Level 2 spec** — remove "colour" from classification attributes (or add secondary cues).
3. **Level 12 spec** — replace colored emoji blocks with shape-differentiated symbols or bundles.
4. **Re-scrape problematic levels** — for levels with >50% flag rate (L26, L29, L31), consider finding B&W-appropriate versions or generating illustrations programmatically.
5. **Set B&W filter at scrape time** — add a pre-simplification preview step before committing images to the question bank.
6. **Use the new stickfigure function as default** in the pipeline (already updated in the notebook).

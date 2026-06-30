"""
run_pipeline.py — Orchestrates the complete FLN Worksheet Analysis Pipeline

Stages:
  1. EXTRACT — Extract images from .docx files (if any exist)
  2. PACKAGE  — Prepare images for Kaggle processing (zip them)
  3. PROCESS  — Organize Kaggle output into structured data/
  4. REPORT   — Generate HTML report from structured data

Usage:
  python run_pipeline.py              # Run full pipeline
  python run_pipeline.py --stage 1    # Run only EXTRACT
  python run_pipeline.py --stage 2    # Run only PACKAGE
  python run_pipeline.py --stage 3    # Run only PROCESS
  python run_pipeline.py --stage 4    # Run only REPORT
  python run_pipeline.py --help       # Show full help
"""

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent

# Stage 1: Extraction
EXTRACT_DIR   = ROOT / "image_extraction_from_docx"
EXTRACT_SCRIPT = EXTRACT_DIR / "extract_images.py"

# Stage 2: Packaging (images → zip for Kaggle)
PACKAGE_OUT    = ROOT / "kaggle_input"
PACKAGE_ZIP    = ROOT / "kaggle_input.zip"

# Stage 3: Processing (Kaggle results → structured data)
PROCESS_INPUT  = ROOT / "kaggle_results"        # extracted FLN_Results from Kaggle
STRUCTURED_DIR = ROOT / "structure_img_with_question" / "data"

# Stage 4: Report
REPORT_SCRIPT  = ROOT / "structure_img_with_question" / "generate_report.py"
REPORT_OUTPUT  = ROOT / "structure_img_with_question" / "question_report.html"


# ── Helpers ──────────────────────────────────────────────────────────────────

def banner(stage: str, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Stage {stage}: {title}")
    print(f"{'='*60}")


def step(msg: str) -> None:
    print(f"  >> {msg}")


# ── Stage 1: Extract images from .docx ───────────────────────────────────────

def stage_extract() -> None:
    banner("1", "EXTRACT — Images from .docx")

    docx_files = sorted(EXTRACT_DIR.glob("*.docx"))
    if not docx_files:
        step("No .docx files found — skipping extraction.")
        return

    step(f"Found {len(docx_files)} .docx file(s): {[p.name for p in docx_files]}")

    # Import and run the extraction function
    sys.path.insert(0, str(EXTRACT_DIR))
    from extract_images import extract_images_in_order

    for docx_path in docx_files:
        images = extract_images_in_order(docx_path, EXTRACT_DIR)
        step(f"{docx_path.name}: extracted {len(images)} image(s)")


# ── Stage 2: Package images for Kaggle ───────────────────────────────────────

def stage_package() -> None:
    banner("2", "PACKAGE — Prepare Kaggle input zip")

    # Collect all images from extraction output and any direct images
    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    images = []

    # From extraction subfolders (e.g. image_extraction_from_docx/1.0/)
    for sub in EXTRACT_DIR.iterdir():
        if sub.is_dir():
            for img in sub.iterdir():
                if img.suffix.lower() in image_extensions:
                    images.append(img)

    # From a manual input folder if it exists
    manual_input = ROOT / "manual_input"
    if manual_input.exists():
        for img in manual_input.iterdir():
            if img.suffix.lower() in image_extensions:
                images.append(img)

    if not images:
        step("No images found to package.")
        return

    # Clean output dir
    if PACKAGE_OUT.exists():
        shutil.rmtree(PACKAGE_OUT)
    PACKAGE_OUT.mkdir(parents=True, exist_ok=True)

    # Copy images with numbered names
    for idx, img in enumerate(sorted(images), 1):
        ext = img.suffix.lower()
        dst = PACKAGE_OUT / f"image{idx}{ext}"
        shutil.copy2(img, dst)

    step(f"Copied {len(images)} image(s) to {PACKAGE_OUT}")

    # Create zip
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()

    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in sorted(PACKAGE_OUT.iterdir()):
            zf.write(img, arcname=img.name)

    step(f"Created {PACKAGE_ZIP.name} ({len(images)} images)")


# ── Stage 3: Process Kaggle results ──────────────────────────────────────────

def stage_process() -> None:
    banner("3", "PROCESS — Organize Kaggle results into structured data/")

    if not PROCESS_INPUT.exists():
        step(f"{PROCESS_INPUT} not found. Copy your Kaggle FLN_Results folder here.")
        return

    # Find all result JSONs and images from Kaggle output
    image_extensions = {".png", ".jpg", ".jpeg"}
    kaggle_images = {}
    kaggle_jsons = {}

    for f in PROCESS_INPUT.rglob("*"):
        if f.suffix.lower() in image_extensions:
            key = f.stem
            kaggle_images[key] = f
        elif f.name.endswith("_result.json"):
            key = f.stem.replace("_result", "")
            kaggle_jsons[key] = f

    if not kaggle_jsons:
        step("No result JSONs found in kaggle_results/.")
        return

    # Ensure structured data directory exists
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for key in sorted(kaggle_jsons.keys()):
        json_path = kaggle_jsons[key]
        img_path = kaggle_images.get(key)

        if not img_path:
            step(f"  Skipping {key}: no matching image found.")
            continue

        # Create per-image folder
        img_folder = STRUCTURED_DIR / key
        img_folder.mkdir(parents=True, exist_ok=True)

        # Copy image
        dst_img = img_folder / img_path.name
        shutil.copy2(img_path, dst_img)

        # Copy / write JSON
        dst_json = img_folder / f"{key}_result.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        dst_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        manifest_entries.append({
            "file": img_path.name,
            "confidence": data.get("confidence_score", 100),
            "question_type": data.get("question_type", "Unknown"),
        })

        step(f"  {key}: {data.get('question_type', '?')} | {data.get('estimated_grade', '?')}")

    # Write batch_manifest.json
    manifest = {"batch": manifest_entries}
    manifest_path = STRUCTURED_DIR / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    step(f"Processed {len(manifest_entries)} question(s)")
    step(f"Manifest written to data/batch_manifest.json")


# ── Stage 4: Generate HTML report ────────────────────────────────────────────

def stage_report() -> None:
    banner("4", "REPORT — Generate HTML report from structured data")

    if not (STRUCTURED_DIR / "batch_manifest.json").exists():
        step("No batch_manifest.json found. Run --stage 3 first or add data manually.")
        return

    sys.path.insert(0, str(STRUCTURED_DIR.parent))
    # The generate_report module expects to be run from its own directory
    import generate_report

    # Reload to ensure fresh execution
    import importlib
    importlib.reload(generate_report)

    generate_report.build_html()

    if REPORT_OUTPUT.exists():
        step(f"Report generated: {REPORT_OUTPUT}")
    else:
        step("Warning: report file not found after generation.")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FLN Worksheet Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--stage", type=int, choices=[1, 2, 3, 4],
        help="Run a single stage (1=EXTRACT, 2=PACKAGE, 3=PROCESS, 4=REPORT)",
    )
    args = parser.parse_args()

    stages = [args.stage] if args.stage else [1, 2, 3, 4]

    for s in stages:
        if s == 1:
            stage_extract()
        elif s == 2:
            stage_package()
        elif s == 3:
            stage_process()
        elif s == 4:
            stage_report()

    banner("✓", "Pipeline complete")


if __name__ == "__main__":
    main()

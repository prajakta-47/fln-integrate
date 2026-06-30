import os
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from PIL import Image
from collections import defaultdict

from fln_ai.config import RAW_DIR, PROCESSED_DIR, SUPPORTED_IMG_EXTS, SUPPORTED_DOC_EXTS

logger = logging.getLogger(__name__)


class DatasetManager:
    """Dataset Management Layer — validate, convert PDFs, deduplicate, assign metadata."""

    def __init__(self, raw_dir=None, processed_dir=None):
        self.raw_dir = Path(raw_dir or RAW_DIR)
        self.processed_dir = Path(processed_dir or PROCESSED_DIR)
        self.manifest = {}

    # ── Ingestion ──────────────────────────────────────────

    def ingest_path(self, path: str | Path) -> list[dict]:
        """Ingest a file or directory into the raw dataset."""
        path = Path(path)
        if path.is_dir():
            return self._ingest_directory(path)
        return [self._ingest_file(path)]

    def _ingest_directory(self, directory: Path) -> list[dict]:
        results = []
        for ext in SUPPORTED_IMG_EXTS | SUPPORTED_DOC_EXTS:
            for fp in sorted(directory.rglob(f"*{ext}")):
                results.append(self._ingest_file(fp))
        return results

    def _ingest_file(self, path: Path) -> dict:
        ext = path.suffix.lower()
        if ext in SUPPORTED_DOC_EXTS:
            return self._handle_pdf(path)
        elif ext in SUPPORTED_IMG_EXTS:
            return self._handle_image(path)
        else:
            logger.warning("Unsupported file: %s", path)
            return {"status": "skipped", "path": str(path), "reason": "unsupported_format"}

    def _handle_image(self, path: Path) -> dict:
        dest = self.raw_dir / path.name
        shutil.copy2(path, dest)
        logger.info("Copied image: %s", dest)
        return {"status": "ingested", "path": str(dest), "type": "image", "source": str(path)}

    def _handle_pdf(self, path: Path) -> dict:
        """Convert PDF pages to images. Requires PyMuPDF."""
        try:
            import fitz
        except ImportError:
            logger.error("PyMuPDF not installed. Install with: pip install pymupdf")
            return {"status": "error", "path": str(path), "reason": "pymupdf_missing"}

        doc = fitz.open(str(path))
        pages = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img_path = self.raw_dir / f"{path.stem}_page_{i+1:03d}.png"
            pix.save(str(img_path))
            pages.append(str(img_path))
            logger.info("Extracted page: %s", img_path)
        doc.close()
        return {"status": "converted", "pages": pages, "source": str(path)}

    # ── Validation ─────────────────────────────────────────

    def validate_images(self) -> list[dict]:
        """Check all raw images for corruption, size, and format."""
        results = []
        for fp in sorted(self.raw_dir.iterdir()):
            if fp.suffix.lower() not in SUPPORTED_IMG_EXTS:
                continue
            record = {"file": str(fp), "valid": True, "width": 0, "height": 0, "issues": []}
            try:
                with Image.open(fp) as img:
                    img.verify()
                with Image.open(fp) as img:
                    w, h = img.size
                record["width"], record["height"] = w, h
                if w < 100 or h < 100:
                    record["issues"].append("too_small")
                    record["valid"] = False
                if fp.stat().st_size == 0:
                    record["issues"].append("empty_file")
                    record["valid"] = False
            except Exception as e:
                record["valid"] = False
                record["issues"].append(str(e))
            results.append(record)
        return results

    # ── Deduplication ──────────────────────────────────────

    def remove_duplicates(self) -> list[dict]:
        """Remove perceptual-duplicate images using MD5 hash."""
        hashes = defaultdict(list)
        for fp in sorted(self.raw_dir.iterdir()):
            if fp.suffix.lower() not in SUPPORTED_IMG_EXTS:
                continue
            h = self._md5(fp)
            hashes[h].append(fp)

        removed = []
        for h, paths in hashes.items():
            if len(paths) > 1:
                for dup in paths[1:]:
                    dup.rename(dup.with_suffix(dup.suffix + ".dup"))
                    removed.append({"hash": h, "kept": str(paths[0]), "removed": str(dup)})
                    logger.info("Duplicate removed: %s", dup)
        return removed

    @staticmethod
    def _md5(path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    # ── Metadata Assignment ────────────────────────────────

    def assign_metadata(self, worksheet_id: str = "", publisher: str = "") -> dict:
        """Assign a metadata record to the current batch."""
        record = {
            "worksheet_id": worksheet_id or f"WS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "publisher": publisher or "unknown",
            "ingested_at": datetime.now().isoformat(),
            "file_count": len(list(self.raw_dir.iterdir())),
        }
        self.manifest = record
        return record

    # ── Move to Processing ────────────────────────────────

    def stage_processed(self) -> list[Path]:
        """Copy validated raw images to processed directory for next pipeline stage."""
        for fp in sorted(self.raw_dir.iterdir()):
            if fp.suffix.lower() not in SUPPORTED_IMG_EXTS or fp.name.endswith(".dup"):
                continue
            shutil.copy2(fp, self.processed_dir / fp.name)
        return sorted(self.processed_dir.iterdir())

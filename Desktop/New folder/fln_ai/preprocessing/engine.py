import cv2
import numpy as np
import logging
from pathlib import Path

from fln_ai.config import (
    PREPROCESS_TARGET_SIZE, PREPROCESS_DESKEW_THRESHOLD,
    PREPROCESS_BLUR_THRESHOLD, PREPROCESS_CONTRAST_THRESHOLD,
    PREPROCESS_CLAHE_CLIP, PREPROCESS_CLAHE_TILE,
)

logger = logging.getLogger(__name__)


class PreprocessingEngine:
    """Image Preprocessing Engine — deskew, resize, contrast, noise removal, threshold."""

    @staticmethod
    def process(img: np.ndarray) -> tuple[np.ndarray, dict]:
        """Run full preprocessing pipeline. Returns (cleaned_image, info_dict)."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        result = img.copy()
        applied = []

        is_blurry = lap_var < PREPROCESS_BLUR_THRESHOLD
        is_small = min(h, w) < PREPROCESS_TARGET_SIZE
        is_low_contrast = (float(gray.max()) - float(gray.min())) < PREPROCESS_CONTRAST_THRESHOLD

        # ── Deskew ────────────────────────────────────────
        angle = self._detect_skew(gray)
        is_skewed = abs(angle) > PREPROCESS_DESKEW_THRESHOLD
        if is_skewed:
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            result = cv2.warpAffine(result, M, (w, h),
                                    flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            applied.append(f"deskew_{angle:.1f}deg")
            h, w = result.shape[:2]

        # ── Noise Removal (bilateral filter) ──────────────
        result = cv2.bilateralFilter(result, d=5, sigmaColor=50, sigmaSpace=50)
        applied.append("denoise")

        # ── Unsharp Mask (if blurry) ──────────────────────
        if is_blurry:
            blurred = cv2.GaussianBlur(result, (0, 0), 3.0)
            sharp = cv2.addWeighted(result, 1.5, blurred, -0.5, 0)
            sharp = np.clip(sharp, 0, 255).astype(np.uint8)
            new_var = cv2.Laplacian(
                cv2.cvtColor(sharp, cv2.COLOR_RGB2GRAY), cv2.CV_64F
            ).var()
            if new_var > lap_var:
                result = sharp
                applied.append("unsharp")

        # ── CLAHE (contrast) ──────────────────────────────
        if is_low_contrast or is_blurry:
            lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(
                clipLimit=PREPROCESS_CLAHE_CLIP,
                tileGridSize=(PREPROCESS_CLAHE_TILE, PREPROCESS_CLAHE_TILE),
            )
            l = clahe.apply(l)
            result = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
            applied.append("clahe")

        # ── Adaptive Threshold (grayscale version for OCR) ─
        gray_result = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)
        thresholded = cv2.adaptiveThreshold(
            gray_result, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 21, 4,
        )
        applied.append("adaptive_thresh")

        # ── Resize ────────────────────────────────────────
        if is_small:
            scale = max(1.0, PREPROCESS_TARGET_SIZE / min(h, w))
            if scale > 1.1:
                result = cv2.resize(result, None, fx=scale, fy=scale,
                                    interpolation=cv2.INTER_CUBIC)
                applied.append(f"upscale_{scale:.1f}x")

        info = {
            "blurry": is_blurry,
            "skewed": is_skewed,
            "small": is_small,
            "low_contrast": is_low_contrast,
            "lap_var": round(lap_var, 1),
            "angle": round(angle, 1),
            "original_size": f"{img.shape[1]}x{img.shape[0]}",
            "applied": applied,
        }
        return result, info

    @staticmethod
    def _detect_skew(gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        if lines is None:
            return 0.0
        angles = []
        for line in lines:
            theta = line[0][1]
            deg = np.degrees(theta) - 90
            if abs(deg) < 30:
                angles.append(deg)
        return float(np.median(angles)) if angles else 0.0

    @staticmethod
    def process_file(image_path: str | Path) -> tuple[np.ndarray, dict]:
        """Load image from disk, preprocess, return (image, info)."""
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return PreprocessingEngine.process(img)

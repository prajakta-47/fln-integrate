# Image Extraction from DOCX

Extracts images from `.docx` files in document order by parsing the XML archive.

## Files

| File | Purpose |
|------|---------|
| `extract_images.py` | Core extraction function — finds `<a:blip>` elements and saves images as `image_001.png`, `image_002.jpg`, etc. |

## Usage

```bash
python extract_images.py
```

Place `.docx` files in this directory. Images are saved into subfolders named after each docx file.

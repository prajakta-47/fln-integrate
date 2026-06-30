import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}


def extract_images_in_order(docx_path: Path, output_dir: Path) -> list[Path]:
    docx_name = docx_path.stem
    out = output_dir / docx_name
    out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path, 'r') as z:
        doc_xml = z.read('word/document.xml')
        rels_xml = z.read('word/_rels/document.xml.rels')

    # Build rId -> target path mapping
    rels_root = ET.fromstring(rels_xml)
    rel_map = {}
    for rel in rels_root:
        rid = rel.get('Id')
        target = rel.get('Target')
        if rid and target:
            rel_map[rid] = target

    # Find all <a:blip> elements in document order
    doc_root = ET.fromstring(doc_xml)
    blips = doc_root.findall('.//a:blip', NS)

    seen = set()
    ordered_paths = []
    for blip in blips:
        rid = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if rid and rid in rel_map:
            img_rel = rel_map[rid]
            img_path = f'word/{img_rel}'
            if img_path not in seen:
                seen.add(img_path)
                ordered_paths.append(img_path)

    extracted = []
    with zipfile.ZipFile(docx_path, 'r') as z:
        for idx, img_zip_path in enumerate(ordered_paths, 1):
            img_data = z.read(img_zip_path)
            ext = Path(img_zip_path).suffix
            new_name = f'image_{idx:03d}{ext}'
            img_path = out / new_name
            img_path.write_bytes(img_data)
            extracted.append(img_path)

    return extracted


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    docx_files = sorted(script_dir.glob('*.docx'))

    if not docx_files:
        print('No .docx files found.')
    else:
        for docx_path in docx_files:
            images = extract_images_in_order(docx_path, script_dir)
            print(f'{docx_path.name}: extracted {len(images)} image(s)')
            for img in images:
                print(f'  -> {img}')

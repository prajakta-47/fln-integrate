import json, hashlib
from pathlib import Path
from xml.sax.saxutils import escape

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_HTML = Path(__file__).parent / "question_paper.html"

def safe(val):
    return str(val).strip() if val is not None else ""

def build_instruction(data):
    heading = safe(data.get("question_heading"))
    action = safe(data.get("student_action"))
    detected = safe(data.get("all_text_detected"))
    if heading in ("None visible", "None", ""): heading = ""
    short = {"circle", "match", "color", "colour", "count", "circle and draw"}
    inst = action if action and action.lower() not in short else (detected if detected else action)
    parts = [p for p in [heading, inst] if p and p != heading]
    return " | ".join(parts) if parts else (heading or action or detected or "")

N = ' fill="none" stroke="#000"'
N1 = N + ' stroke-width="1.3"'
N2 = N + ' stroke-width="1.2"'

def A(key): return ANIMALS[key]
def O(key): return OBJS[key]
def S(key): return SHAPES[key]

ANIMALS = {
  "ele": '<svg viewBox="0 0 50 40" width="42" height="34"><ellipse cx="25" cy="22" rx="18" ry="14"' + N1 + '/><circle cx="16" cy="13" r="8"' + N1 + '/><circle cx="14" cy="12" r="1" fill="#000"/><path d="M34 30 Q38 35 36 40" stroke="#000" stroke-width="1.8" fill="none" stroke-linecap="round"/><ellipse cx="8" cy="20" rx="3" ry="4"' + N1 + '/><ellipse cx="42" cy="20" rx="3" ry="4"' + N1 + '/></svg>',
  "mou": '<svg viewBox="0 0 24 18" width="20" height="15"><ellipse cx="12" cy="11" rx="8" ry="6"' + N1 + '/><circle cx="11" cy="7" r="4.5"' + N1 + '/><circle cx="10.5" cy="6.5" r="0.7" fill="#000"/><circle cx="13" cy="6.5" r="0.7" fill="#000"/><path d="M4 13 Q2 16 5 17" stroke="#000" stroke-width="1" fill="none"/><path d="M20 13 Q22 16 19 17" stroke="#000" stroke-width="1" fill="none"/></svg>',
  "cat": '<svg viewBox="0 0 30 22" width="26" height="19"><ellipse cx="15" cy="14" rx="10" ry="7"' + N1 + '/><circle cx="12" cy="9" r="5"' + N1 + '/><polygon points="9,3 11,7 8,7"' + N1 + '/><polygon points="15,3 13,7 16,7"' + N1 + '/><circle cx="11" cy="8.5" r="0.7" fill="#000"/><circle cx="14" cy="8.5" r="0.7" fill="#000"/><path d="M8 16 Q6 18 9 19" stroke="#000" stroke-width="1" fill="none"/><path d="M22 16 Q24 18 21 19" stroke="#000" stroke-width="1" fill="none"/></svg>',
  "dog": '<svg viewBox="0 0 30 24" width="26" height="21"><ellipse cx="17" cy="15" rx="10" ry="8"' + N1 + '/><ellipse cx="10" cy="10" rx="6" ry="5"' + N1 + '/><ellipse cx="10" cy="12" rx="2" ry="1.5" fill="#000" opacity="0.3"/><circle cx="9" cy="9" r="0.7" fill="#000"/><circle cx="12.5" cy="9" r="0.7" fill="#000"/><path d="M10 4 Q12 1 14 4" stroke="#000" stroke-width="1" fill="none"/><ellipse cx="24" cy="12" rx="2.5" ry="1.5"' + N1 + '/></svg>',
  "gir": '<svg viewBox="0 0 18 40" width="15" height="36"><line x1="9" y1="8" x2="9" y2="36" stroke="#000" stroke-width="2.5" stroke-linecap="round"/><ellipse cx="9" cy="5" rx="5" ry="4"' + N1 + '/><circle cx="8" cy="4.5" r="0.6" fill="#000"/><line x1="6" y1="10" x2="14" y2="12" stroke="#000" stroke-width="1"/><line x1="5" y1="34" x2="3" y2="39" stroke="#000" stroke-width="1.5" stroke-linecap="round"/><line x1="13" y1="34" x2="15" y2="39" stroke="#000" stroke-width="1.5" stroke-linecap="round"/></svg>',
  "but": '<svg viewBox="0 0 30 22" width="26" height="19"><ellipse cx="15" cy="11" rx="2" ry="6"' + N2 + '/><ellipse cx="8" cy="8" rx="6" ry="5"' + N1 + '/><ellipse cx="22" cy="8" rx="6" ry="5"' + N1 + '/><ellipse cx="8" cy="16" rx="5" ry="3"' + N1 + '/><ellipse cx="22" cy="16" rx="5" ry="3"' + N1 + '/></svg>',
  "fsh": '<svg viewBox="0 0 28 14" width="24" height="12"><ellipse cx="12" cy="7" rx="9" ry="5"' + N1 + '/><polygon points="20,2 28,7 20,12"' + N1 + '/><circle cx="8" cy="6" r="1" fill="#000"/><path d="M12 5 L14 7 L12 9" fill="none" stroke="#000" stroke-width="0.8"/></svg>',
  "brd": '<svg viewBox="0 0 22 18" width="19" height="15"><ellipse cx="12" cy="10" rx="7" ry="5"' + N1 + '/><circle cx="9" cy="7" r="4"' + N1 + '/><circle cx="8" cy="6.5" r="0.6" fill="#000"/><polygon points="12,3 14,6 11,6" fill="none" stroke="#000" stroke-width="1"/><path d="M19 8 Q22 6 20 4" stroke="#000" stroke-width="1" fill="none"/><line x1="15" y1="14" x2="14" y2="17" stroke="#000" stroke-width="1" stroke-linecap="round"/><line x1="17" y1="13" x2="18" y2="17" stroke="#000" stroke-width="1" stroke-linecap="round"/></svg>',
}

OBJS = {
  "tree": '<svg viewBox="0 0 20 34" width="17" height="30"><rect x="7" y="18" width="6" height="14" rx="1"' + N1 + '/><polygon points="10,2 2,18 18,18"' + N1 + '/></svg>',
  "hous": '<svg viewBox="0 0 28 24" width="24" height="20"><polygon points="2,10 14,1 26,10"' + N1 + '/><rect x="5" y="10" width="18" height="12" rx="1"' + N1 + '/><rect x="11" y="15" width="6" height="7"' + N1 + '/></svg>',
  "appl": '<svg viewBox="0 0 16 18" width="14" height="16"><ellipse cx="8" cy="10" rx="6" ry="7"' + N1 + '/><path d="M8 3 Q9.5 1.5 11 3" stroke="#000" stroke-width="0.8" fill="none"/><line x1="8" y1="4" x2="8" y2="6" stroke="#000" stroke-width="0.6"/></svg>',
  "mngo": '<svg viewBox="0 0 16 16" width="14" height="14"><ellipse cx="8" cy="9" rx="6" ry="7"' + N1 + '/><path d="M8 2 Q9.5 0.5 11 2" stroke="#000" stroke-width="0.8" fill="none"/></svg>',
  "bana": '<svg viewBox="0 0 18 14" width="16" height="12"><path d="M3 11 Q6 2 14 1 Q11 5 9 9 Q7 11 3 11"' + N1 + '/></svg>',
  "book": '<svg viewBox="0 0 18 20" width="16" height="18"><rect x="3" y="2" width="14" height="16" rx="1"' + N1 + '/><line x1="6" y1="6" x2="14" y2="6" stroke="#000" stroke-width="0.8"/><line x1="6" y1="10" x2="12" y2="10" stroke="#000" stroke-width="0.8"/></svg>',
  "penc": '<svg viewBox="0 0 6 26" width="5" height="24"><polygon points="3,2 1,8 5,8"' + N1 + '/><rect x="1.5" y="8" width="3" height="16" rx="0.3"' + N1 + '/></svg>',
  "star": '<svg viewBox="0 0 18 18" width="16" height="16"><polygon points="9,1 11,6 17,6 12,10 14,16 9,12 4,16 6,10 1,6 7,6"' + N1 + '/></svg>',
  "ball": '<svg viewBox="0 0 18 18" width="16" height="16"><circle cx="9" cy="9" r="8"' + N1 + '/><line x1="9" y1="1" x2="9" y2="17" stroke="#000" stroke-width="0.6"/><line x1="1" y1="9" x2="17" y2="9" stroke="#000" stroke-width="0.6"/><ellipse cx="9" cy="9" rx="5.6" ry="8"' + N2 + '/></svg>',
  "flow": '<svg viewBox="0 0 16 18" width="14" height="16"><circle cx="8" cy="8" r="2.5"' + N1 + '/><circle cx="8" cy="2.5" r="2.5"' + N1 + '/><circle cx="13.5" cy="5.5" r="2.5"' + N1 + '/><circle cx="13.5" cy="10.5" r="2.5"' + N1 + '/><circle cx="8" cy="13.5" r="2.5"' + N1 + '/><circle cx="2.5" cy="10.5" r="2.5"' + N1 + '/><circle cx="2.5" cy="5.5" r="2.5"' + N1 + '/><line x1="8" y1="13" x2="8" y2="17" stroke="#000" stroke-width="1"/></svg>',
  "jar": '<svg viewBox="0 0 14 18" width="12" height="16"><rect x="3" y="4" width="8" height="12" rx="1"' + N1 + '/><rect x="1" y="2" width="12" height="3" rx="1"' + N1 + '/></svg>',
  "cake": '<svg viewBox="0 0 22 18" width="19" height="16"><rect x="3" y="6" width="16" height="10" rx="1"' + N1 + '/><rect x="5" y="2" width="12" height="6" rx="2"' + N1 + '/><line x1="5" y1="6" x2="17" y2="6" stroke="#000" stroke-width="0.8"/><circle cx="9" cy="9" r="0.8" fill="#000"/><circle cx="13" cy="9" r="0.8" fill="#000"/></svg>',
}

SHAPES = {
  "circ": '<svg viewBox="0 0 22 22" width="20" height="20"><circle cx="11" cy="11" r="9"' + N1 + '/></svg>',
  "squr": '<svg viewBox="0 0 22 22" width="20" height="20"><rect x="2" y="2" width="18" height="18" rx="1"' + N1 + '/></svg>',
  "trng": '<svg viewBox="0 0 22 22" width="20" height="20"><polygon points="11,1 21,21 1,21"' + N1 + '/></svg>',
  "diam": '<svg viewBox="0 0 22 22" width="20" height="20"><polygon points="11,1 21,11 11,21 1,11"' + N1 + '/></svg>',
  "hart": '<svg viewBox="0 0 22 20" width="20" height="18"><path d="M11 18 C4 12 1 7 5 3 C8 0 11 3 11 3 C11 3 14 0 17 3 C21 7 18 12 11 18"' + N1 + '/></svg>',
}

def TK():
  return '<svg viewBox="0 0 14 14" width="12" height="12"><circle cx="7" cy="7" r="6" fill="none" stroke="#000" stroke-width="1.2"/><polyline points="4,7 6.5,9.5 10,5" fill="none" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

def CR():
  return '<svg viewBox="0 0 14 14" width="12" height="12"><circle cx="7" cy="7" r="6" fill="none" stroke="#000" stroke-width="1.2"/><line x1="4" y1="4" x2="10" y2="10" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="10" y1="4" x2="4" y2="10" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'

STICK = '<svg viewBox="0 0 18 30" width="16" height="28"><circle cx="9" cy="4.5" r="3" fill="none" stroke="#000" stroke-width="1.2"/><line x1="9" y1="7.5" x2="9" y2="20" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="12" x2="3" y2="16" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="12" x2="15" y2="16" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="5" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="13" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'
STICK_A = '<svg viewBox="0 0 18 30" width="16" height="28"><circle cx="9" cy="4.5" r="3" fill="none" stroke="#000" stroke-width="1.2"/><line x1="9" y1="7.5" x2="9" y2="20" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="3" y1="10" x2="9" y2="14" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="14" x2="15" y2="10" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="5" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="13" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'
STICK_W = '<svg viewBox="0 0 18 30" width="16" height="28"><circle cx="9" cy="4.5" r="3" fill="none" stroke="#000" stroke-width="1.2"/><line x1="9" y1="7.5" x2="9" y2="20" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="13" x2="15" y2="9" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="13" x2="3" y2="16" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="5" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="13" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'
STICK_F = '<svg viewBox="0 0 18 30" width="16" height="28"><circle cx="9" cy="4.5" r="3" fill="none" stroke="#000" stroke-width="1.2"/><line x1="9" y1="7.5" x2="9" y2="20" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="6" y1="11" x2="12" y2="11" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="5" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="20" x2="13" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'
STICK_L = '<svg viewBox="0 0 18 30" width="16" height="28"><circle cx="9" cy="4.5" r="3" fill="none" stroke="#000" stroke-width="1.2"/><line x1="9" y1="7.5" x2="9" y2="20" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="12" x2="3" y2="16" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="12" x2="15" y2="16" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="6.5" y1="21" x2="4" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="9" y1="21" x2="9" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/><line x1="11.5" y1="21" x2="14" y2="27" stroke="#000" stroke-width="1.2" stroke-linecap="round"/></svg>'

# ─── Question Block Generators ────────────────────────────────────

def class_block(data):
    h = (safe(data.get("question_heading")) + safe(data.get("all_text_detected"))).lower()
    if "big" in h and "small" in h:
        return '<table class="q-table class-table"><tr><td class="class-col"><div class="class-head">BIG</div><div class="class-items"><div class="citem">' + A("ele") + '<span class="clabel">Elephant</span></div><div class="citem">' + O("hous") + '<span class="clabel">House</span></div><div class="citem">' + O("tree") + '<span class="clabel">Tree</span></div></div></td><td class="class-col"><div class="class-head">SMALL</div><div class="class-items"><div class="citem">' + A("mou") + '<span class="clabel">Mouse</span></div><div class="citem">' + O("appl") + '<span class="clabel">Apple</span></div><div class="citem">' + O("penc") + '<span class="clabel">Pencil</span></div></div></td></tr></table>'
    if "thick" in h and "thin" in h:
        return '<table class="q-table class-table"><tr><td class="class-col"><div class="class-head">THICK</div><div class="class-items"><div class="citem"><svg viewBox="0 0 36 40" width="32" height="36"><rect x="4" y="6" width="28" height="30" rx="2"' + N1 + '/><rect x="2" y="4" width="28" height="30" rx="2"' + N1 + '/><line x1="8" y1="14" x2="26" y2="14" stroke="#000" stroke-width="1.2"/><line x1="8" y1="20" x2="22" y2="20" stroke="#000" stroke-width="1.2"/></svg><span class="clabel">Book</span></div><div class="citem"><svg viewBox="0 0 28 22" width="25" height="20"><rect x="2" y="2" width="24" height="3" rx="1.5"' + N1 + '/><rect x="1" y="7" width="26" height="3" rx="1.5"' + N1 + '/><rect x="2" y="12" width="24" height="3" rx="1.5"' + N1 + '/><rect x="1" y="17" width="26" height="3" rx="1.5"' + N1 + '/></svg><span class="clabel">Burger</span></div><div class="citem">' + O("tree") + '<span class="clabel">Tree</span></div></div></td><td class="class-col"><div class="class-head">THIN</div><div class="class-items"><div class="citem"><svg viewBox="0 0 24 34" width="21" height="30"><rect x="3" y="4" width="18" height="28" rx="1"' + N1 + '/><line x1="7" y1="12" x2="17" y2="12" stroke="#000" stroke-width="0.8"/><line x1="7" y1="17" x2="15" y2="17" stroke="#000" stroke-width="0.8"/></svg><span class="clabel">Notebook</span></div><div class="citem">' + O("penc") + '<span class="clabel">Pencil</span></div><div class="citem"><svg viewBox="0 0 20 20" width="18" height="18"><circle cx="10" cy="10" r="8"' + N1 + '/><circle cx="7" cy="7" r="2"' + N1 + '/><circle cx="13" cy="7" r="1.5"' + N1 + '/><circle cx="10" cy="6.5" r="1.8"' + N1 + '/></svg><span class="clabel">Pizza</span></div></div></td></tr></table>'
    if "light" in h or "heavy" in h:
        return '<table class="q-table class-table"><tr><td class="class-col"><div class="class-head">LIGHT</div><div class="class-items"><div class="citem"><svg viewBox="0 0 14 20" width="12" height="18"><rect x="3" y="2" width="8" height="14" rx="1"' + N1 + '/><rect x="4" y="2" width="6" height="10" fill="#000" opacity="0.15"/></svg><span class="clabel">Glass</span></div><div class="citem">' + O("penc") + '<span class="clabel">Pencil</span></div><div class="citem">' + O("ball") + '<span class="clabel">Ball</span></div></div></td><td class="class-col"><div class="class-head">HEAVY</div><div class="class-items"><div class="citem"><svg viewBox="0 0 20 20" width="18" height="18"><rect x="1" y="1" width="18" height="17" rx="2"' + N1 + '/><path d="M6 18 L10 20 L14 18" stroke="#000" stroke-width="1" fill="none"/></svg><span class="clabel">Bucket</span></div><div class="citem">' + O("book") + '<span class="clabel">Book</span></div><div class="citem"><svg viewBox="0 0 18 18" width="16" height="16"><circle cx="10" cy="9" r="7"' + N1 + '/><circle cx="5" cy="7" r="2.5"' + N1 + '/></svg><span class="clabel">Pumpkin</span></div></div></td></tr></table>'
    return ""

def comp_block(data):
    h = (safe(data.get("question_heading")) + safe(data.get("all_text_detected"))).lower()
    if "tall" in h and "short" in h:
        return '<table class="q-table compare-table"><tr><td class="cpair"><svg viewBox="0 0 16 42" width="14" height="38"><rect x="2" y="10" width="12" height="28" rx="2"' + N1 + '/><rect x="0" y="6" width="16" height="6" rx="1.5"' + N1 + '/></svg><span class="vslabel">vs</span><svg viewBox="0 0 14 24" width="12" height="21"><rect x="1" y="4" width="12" height="18" rx="2"' + N1 + '/><rect x="0" y="2" width="14" height="5" rx="1.5"' + N1 + '/></svg>' + TK() + CR() + '</td><td class="cpair"><svg viewBox="0 0 20 38" width="18" height="34"><rect x="2" y="12" width="16" height="24" rx="2"' + N1 + '/><rect x="3" y="6" width="14" height="8" rx="1.5"' + N1 + '/></svg><span class="vslabel">vs</span><svg viewBox="0 0 18 22" width="16" height="19"><rect x="1" y="3" width="16" height="18" rx="2"' + N1 + '/><rect x="2" y="1" width="14" height="5" rx="1.5"' + N1 + '/></svg>' + TK() + CR() + '</td></tr></table>'
    if "heavy" in h or "light" in h:
        return '<table class="q-table compare-table"><tr><td class="cpair">' + A("ele") + '<span class="vslabel">vs</span>' + A("mou") + TK() + '</td><td class="cpair">' + O("book") + '<span class="vslabel">vs</span>' + O("penc") + TK() + '</td></tr></table>'
    if "long" in h or "shortest" in h or "vehicle" in h:
        return '<table class="q-table compare-table"><tr><td class="cpair"><svg viewBox="0 0 34 12" width="30" height="10"><rect x="1" y="1" width="32" height="9" rx="2"' + N1 + '/></svg><svg viewBox="0 0 24 12" width="21" height="10"><rect x="1" y="1" width="22" height="9" rx="2"' + N1 + '/></svg><svg viewBox="0 0 14 12" width="12" height="10"><rect x="1" y="1" width="12" height="9" rx="2"' + N1 + '/></svg><span class="vslabel">Tick the longest</span></td></tr><tr><td class="cpair">' + O("penc") + '<svg viewBox="0 0 12 26" width="10" height="24"><polygon points="6,2 4,8 8,8"' + N1 + '/><rect x="4.5" y="8" width="3" height="16" rx="0.3"' + N1 + '/></svg><svg viewBox="0 0 8 26" width="7" height="24"><polygon points="4,2 2,8 6,8"' + N1 + '/><rect x="3" y="8" width="2" height="16" rx="0.3"' + N1 + '/></svg><span class="vslabel">vs</span></td></tr></table>'
    if "less" in h or "more" in h or "quantity" in h:
        return '<table class="q-table compare-table"><tr><td class="cpair"><svg viewBox="0 0 20 18" width="18" height="16"><rect x="3" y="2" width="14" height="14" rx="1"' + N1 + '/><line x1="5" y1="10" x2="15" y2="10" stroke="#000" stroke-width="0.8"/></svg><span class="vslabel">Less</span><svg viewBox="0 0 20 18" width="18" height="16"><rect x="3" y="2" width="14" height="14" rx="1"' + N1 + '/><line x1="5" y1="6" x2="15" y2="6" stroke="#000" stroke-width="0.8"/><line x1="5" y1="10" x2="15" y2="10" stroke="#000" stroke-width="0.8"/><line x1="5" y1="14" x2="15" y2="14" stroke="#000" stroke-width="0.8"/></svg><span class="vslabel">More</span></td></tr><tr><td class="cpair">' + O("jar") + O("jar") + '<span class="vslabel">vs</span>' + O("jar") + O("jar") + O("jar") + '</td></tr></table>'
    if any(w in h for w in ["water", "vessel", "capacity", "hold", "fill"]):
        return '<table class="q-table compare-table"><tr><td class="cpair"><svg viewBox="0 0 14 24" width="12" height="21"><rect x="2" y="2" width="10" height="18" rx="1"' + N1 + '/><rect x="3" y="14" width="8" height="6" fill="#000" opacity="0.12"/></svg><svg viewBox="0 0 18 20" width="16" height="18"><rect x="2" y="2" width="14" height="16" rx="1"' + N1 + '/><rect x="3" y="8" width="12" height="10" fill="#000" opacity="0.12"/></svg><svg viewBox="0 0 22 26" width="19" height="23"><path d="M3 6 Q3 2 11 2 Q19 2 19 6 L19 24 L3 24 Z"' + N1 + '/><rect x="4" y="12" width="14" height="12" fill="#000" opacity="0.12"/></svg><span class="vslabel">Cross the smallest</span></td></tr></table>'
    if "biggest" in h or "largest" in h:
        return '<table class="q-table compare-table"><tr><td class="cpair"><svg viewBox="0 0 14 14" width="12" height="12"><circle cx="7" cy="7" r="6"' + N1 + '/></svg><svg viewBox="0 0 22 22" width="19" height="19"><circle cx="11" cy="11" r="10"' + N1 + '/></svg><svg viewBox="0 0 30 30" width="26" height="26"><circle cx="15" cy="15" r="14"' + N1 + '/></svg><span class="vslabel">Circle the biggest</span></td></tr><tr><td class="cpair">' + O("appl") + O("appl") + O("appl") + '<span class="vslabel">Circle the biggest</span></td></tr></table>'
    return '<table class="q-table compare-table"><tr><td class="cpair">' + A("ele") + '<span class="vslabel">vs</span>' + A("mou") + '<span class="vslabel label-inline">Circle the bigger one</span></td><td class="cpair">' + A("gir") + '<span class="vslabel">vs</span>' + A("cat") + '<span class="vslabel label-inline">Circle the smaller one</span></td></tr></table>'

def match_block(data):
    h = (safe(data.get("question_heading")) + safe(data.get("all_text_detected")) + safe(data.get("visual_elements"))).lower()
    if any(w in h for w in ["fruit", "apple", "mango", "banana", "grape", "orange"]):
        return '<table class="q-table match-table"><tr><td class="mcol"><div class="mitem"><span class="mdot"></span>' + O("appl") + ' Apple</div><div class="mitem"><span class="mdot"></span>' + O("mngo") + ' Mango</div><div class="mitem"><span class="mdot"></span>' + O("bana") + ' Banana</div></td><td class="marr"><svg viewBox="0 0 50 12" width="45" height="10"><line x1="2" y1="6" x2="46" y2="6" stroke="#000" stroke-width="0.8" stroke-dasharray="4,3"/><polygon points="44,3 48,6 44,9" fill="#000"/></svg></td><td class="mcol"><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div></td></tr></table>'
    if any(w in h for w in ["shape", "circle", "square", "triangle"]):
        left = '<div class="mitem"><span class="mdot"></span>' + S("circ") + '</div><div class="mitem"><span class="mdot"></span>' + S("squr") + '</div><div class="mitem"><span class="mdot"></span>' + S("trng") + '</div>'
        right = '<div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div>'
        return '<table class="q-table match-table"><tr><td class="mcol">' + left + '</td><td class="marr"><svg viewBox="0 0 50 12" width="45" height="10"><line x1="2" y1="6" x2="46" y2="6" stroke="#000" stroke-width="0.8" stroke-dasharray="4,3"/><polygon points="44,3 48,6 44,9" fill="#000"/></svg></td><td class="mcol">' + right + '</td></tr></table>'
    if any(w in h for w in ["school", "backpack", "bus", "bag"]):
        return '<table class="q-table match-table"><tr><td class="mcol"><div class="mitem"><span class="mdot"></span><svg viewBox="0 0 18 20" width="16" height="18"><rect x="3" y="4" width="12" height="14" rx="2"' + N1 + '/><rect x="7" y="2" width="4" height="3" rx="1"' + N1 + '/><path d="M3 10 L15 10" stroke="#000" stroke-width="0.8"/></svg> Bag</div><div class="mitem"><span class="mdot"></span>' + O("book") + ' Book</div><div class="mitem"><span class="mdot"></span>' + O("penc") + ' Pencil</div></td><td class="marr"><svg viewBox="0 0 50 12" width="45" height="10"><line x1="2" y1="6" x2="46" y2="6" stroke="#000" stroke-width="0.8" stroke-dasharray="4,3"/><polygon points="44,3 48,6 44,9" fill="#000"/></svg></td><td class="mcol"><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div></td></tr></table>'
    if any(w in h for w in ["flower", "pot"]):
        return '<table class="q-table match-table"><tr><td class="mcol"><div class="mitem"><span class="mdot"></span>' + O("flow") + '</div><div class="mitem"><span class="mdot"></span>' + O("star") + '</div><div class="mitem"><span class="mdot"></span>' + O("flow") + '</div></td><td class="marr"><svg viewBox="0 0 50 12" width="45" height="10"><line x1="2" y1="6" x2="46" y2="6" stroke="#000" stroke-width="0.8" stroke-dasharray="4,3"/><polygon points="44,3 48,6 44,9" fill="#000"/></svg></td><td class="mcol"><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div></td></tr></table>'
    return '<table class="q-table match-table"><tr><td class="mcol"><div class="mitem"><span class="mdot"></span>' + A("dog") + ' Dog</div><div class="mitem"><span class="mdot"></span>' + O("ball") + ' Ball</div><div class="mitem"><span class="mdot"></span>' + O("tree") + ' Tree</div></td><td class="marr"><svg viewBox="0 0 50 12" width="45" height="10"><line x1="2" y1="6" x2="46" y2="6" stroke="#000" stroke-width="0.8" stroke-dasharray="4,3"/><polygon points="44,3 48,6 44,9" fill="#000"/></svg></td><td class="mcol"><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div><div class="mitem"><span class="mdot"></span><span class="mblank"></span></div></td></tr></table>'

def vocab_block(data):
    return '<table class="q-table opp-table"><tr><td class="opp-num">1.</td><td class="opp-img">' + A("ele") + '<br><span class="opp-label">big</span></td><td class="opp-or">or</td><td class="opp-choice">' + A("mou") + '<br><span>small</span></td><td class="opp-choice faded"><svg viewBox="0 0 18 24" width="16" height="21"><rect x="2" y="2" width="14" height="20" rx="1" fill="none" stroke="#999" stroke-width="1"/></svg><br><span>tall</span></td></tr><tr><td class="opp-num">2.</td><td class="opp-img"><svg viewBox="0 0 18 26" width="16" height="23"><path d="M9 12 L9 4 M9 12 Q6 8 9 4 Q12 8 9 12" fill="none" stroke="#000" stroke-width="1.3"/><path d="M9 12 Q12 15 9 18 Q6 15 9 12" fill="none" stroke="#000" stroke-width="1.3"/><line x1="4" y1="7" x2="6" y2="10" stroke="#000" stroke-width="1" stroke-linecap="round"/><line x1="14" y1="7" x2="12" y2="10" stroke="#000" stroke-width="1" stroke-linecap="round"/></svg><br><span class="opp-label">hot</span></td><td class="opp-or">or</td><td class="opp-choice"><svg viewBox="0 0 18 26" width="16" height="23"><polygon points="9,2 10.5,10 17,10 12,14 13.5,22 9,17 4.5,22 6,14 1,10 7.5,10" fill="none" stroke="#000" stroke-width="1.2"/></svg><br><span>cold</span></td><td class="opp-choice faded"><svg viewBox="0 0 14 14" width="12" height="12"><circle cx="7" cy="7" r="6" fill="none" stroke="#999" stroke-width="1"/></svg><br><span>cool</span></td></tr><tr><td class="opp-num">3.</td><td class="opp-img"><svg viewBox="0 0 18 22" width="16" height="20"><rect x="2" y="2" width="14" height="18" rx="1" fill="none" stroke="#000" stroke-width="1.3"/><polygon points="2,2 9,7 16,2" fill="none" stroke="#000" stroke-width="1.3"/></svg><br><span class="opp-label">in</span></td><td class="opp-or">or</td><td class="opp-choice"><svg viewBox="0 0 18 22" width="16" height="20"><rect x="2" y="2" width="14" height="18" rx="1" fill="none" stroke="#000" stroke-width="1.3"/><polygon points="2,2 9,7 16,2" fill="none" stroke="#000" stroke-width="1.3"/><path d="M6 9 L9 5 L12 9" fill="none" stroke="#000" stroke-width="1.2"/></svg><br><span>out</span></td><td class="opp-choice faded"><svg viewBox="0 0 14 18" width="12" height="16"><line x1="7" y1="2" x2="7" y2="14" stroke="#999" stroke-width="1.3"/><polygon points="7,2 4,6 10,6" fill="none" stroke="#999" stroke-width="1"/></svg><br><span>up</span></td></tr><tr><td class="opp-num">4.</td><td class="opp-img"><svg viewBox="0 0 18 18" width="16" height="16"><circle cx="9" cy="9" r="7" fill="none" stroke="#000" stroke-width="1.3"/><path d="M6 6 Q9 3 12 6 Q9 9 6 6" fill="none" stroke="#000" stroke-width="1"/></svg><br><span class="opp-label">happy</span></td><td class="opp-or">or</td><td class="opp-choice"><svg viewBox="0 0 18 18" width="16" height="16"><circle cx="9" cy="9" r="7" fill="none" stroke="#000" stroke-width="1.3"/><path d="M6 12 Q9 9 12 12" fill="none" stroke="#000" stroke-width="1"/></svg><br><span>sad</span></td><td class="opp-choice faded"><svg viewBox="0 0 16 16" width="14" height="14"><circle cx="8" cy="8" r="6" fill="none" stroke="#999" stroke-width="1"/><line x1="5" y1="5" x2="5" y2="7" stroke="#999" stroke-width="0.8"/><line x1="11" y1="5" x2="11" y2="7" stroke="#999" stroke-width="0.8"/></svg><br><span>loud</span></td></tr></table>'

def shape_block(data):
    h = (safe(data.get("question_heading")) + safe(data.get("all_text_detected"))).lower()
    if "match" in h:
        return '<table class="q-table key-table"><tr><td class="kswatch">' + S("circ") + '<span class="klabel">Circle</span></td><td class="kswatch">' + S("squr") + '<span class="klabel">Square</span></td><td class="kswatch">' + S("trng") + '<span class="klabel">Triangle</span></td><td class="kswatch">' + S("diam") + '<span class="klabel">Diamond</span></td></tr></table><div class="figure-box"><svg viewBox="0 0 200 70" style="width:100%;max-width:300px;"><line x1="20" y1="20" x2="20" y2="50" stroke="#000" stroke-width="0.6" stroke-dasharray="2,2"/><circle cx="50" cy="35" r="14" fill="none" stroke="#000" stroke-width="1.5"/><rect x="72" y="22" width="26" height="26" rx="1" fill="none" stroke="#000" stroke-width="1.5"/><polygon points="117,10 140,60 94,60" fill="none" stroke="#000" stroke-width="1.5"/><polygon points="155,10 170,60 140,60" fill="none" stroke="#000" stroke-width="1.5"/></svg></div>'
    if "colour" in h or "color" in h:
        return '<table class="q-table key-table"><tr><td class="kswatch">' + S("squr") + '<span class="klabel">Square</span></td><td class="kswatch">' + S("trng") + '<span class="klabel">Triangle</span></td><td class="kswatch">' + S("circ") + '<span class="klabel">Circle</span></td></tr></table><div class="figure-box"><svg viewBox="0 0 160 130" style="width:100%;max-width:200px;"><polygon points="80,10 48,42 112,42" fill="none" stroke="#000" stroke-width="2" stroke-dasharray="4,3"/><circle cx="80" cy="62" r="16" fill="none" stroke="#000" stroke-width="2" stroke-dasharray="4,3"/><circle cx="74" cy="59" r="2" fill="#000"/><circle cx="86" cy="59" r="2" fill="#000"/><path d="M72 68 Q80 73 88 68" fill="none" stroke="#000" stroke-width="1.2"/><rect x="66" y="83" width="28" height="34" rx="3" fill="none" stroke="#000" stroke-width="2" stroke-dasharray="4,3"/><line x1="66" y1="92" x2="52" y2="104" stroke="#000" stroke-width="2" stroke-dasharray="3,3"/><line x1="94" y1="92" x2="108" y2="104" stroke="#000" stroke-width="2" stroke-dasharray="3,3"/><line x1="74" y1="117" x2="70" y2="128" stroke="#000" stroke-width="2" stroke-dasharray="3,3"/><line x1="86" y1="117" x2="90" y2="128" stroke="#000" stroke-width="2" stroke-dasharray="3,3"/></svg></div>'
    return '<table class="q-table key-table"><tr><td class="kswatch">' + S("squr") + '<span class="klabel">Square</span></td><td class="kswatch">' + S("trng") + '<span class="klabel">Triangle</span></td><td class="kswatch">' + S("circ") + '<span class="klabel">Circle</span></td><td class="kswatch">' + S("hart") + '<span class="klabel">Heart</span></td></tr></table><div class="figure-box"><svg viewBox="0 0 220 60" style="width:100%;max-width:340px;"><text x="30" y="14" text-anchor="middle" font-size="7" fill="#666">Ball</text><circle cx="30" cy="32" r="14" fill="none" stroke="#000" stroke-width="1.5"/><text x="85" y="14" text-anchor="middle" font-size="7" fill="#666">Book</text><rect x="70" y="18" width="26" height="26" rx="1" fill="none" stroke="#000" stroke-width="1.5"/><text x="140" y="14" text-anchor="middle" font-size="7" fill="#666">House</text><polygon points="140,44 125,18 155,18" fill="none" stroke="#000" stroke-width="1.5"/><rect x="128" y="28" width="24" height="16" rx="1" fill="none" stroke="#000" stroke-width="1.2"/><text x="195" y="14" text-anchor="middle" font-size="7" fill="#666">Star</text><polygon points="195,44 189,32 183,44 191,36 199,44 191,32" fill="none" stroke="#000" stroke-width="1.2"/></svg></div>'

def count_block(data):
    return '<table class="q-table count-table"><tr><td class="ccell"><div class="fruits">' + O("mngo") + O("mngo") + '</div><div class="qmark">?</div></td><td class="ccell"><div class="fruits">' + O("appl") + O("appl") + O("appl") + '</div><div class="qmark">?</div></td><td class="ccell"><div class="fruits">' + O("bana") + O("bana") + O("bana") + O("bana") + '</div><div class="qmark">?</div></td></tr></table>'

def logic_block(data):
    h = (safe(data.get("question_heading")) + safe(data.get("all_text_detected"))).lower()
    if "kite" in h:
        return '<div class="figure-box"><svg viewBox="0 0 160 80" style="width:100%;max-width:260px;"><line x1="40" y1="65" x2="40" y2="20" stroke="#000" stroke-width="1"/><polygon points="40,10 50,20 30,20" fill="none" stroke="#000" stroke-width="1.3"/><text x="40" y="78" text-anchor="middle" font-size="7" fill="#666">Girl</text><rect x="100" y="45" width="30" height="20" fill="none" stroke="#000" stroke-width="1.3"/><polygon points="100,45 115,35 130,45" fill="none" stroke="#000" stroke-width="1.3"/><text x="115" y="78" text-anchor="middle" font-size="7" fill="#666">House</text><text x="80" y="18" text-anchor="middle" font-size="9" font-weight="bold">How will she get the kite?</text></svg></div>'
    if "find" in h or "same" in h:
        return '<table class="q-table stick-table"><tr><td class="scol"><div class="sref">' + STICK + '</div><div class="sopts">' + STICK + STICK_A + STICK_W + '</div></td><td class="scol"><div class="sref">' + STICK_A + '</div><div class="sopts">' + STICK + STICK_F + STICK_L + '</div></td></tr></table>'
    return '<div class="figure-box"><svg viewBox="0 0 200 50" style="width:100%;max-width:300px;"><circle cx="40" cy="25" r="10" fill="none" stroke="#000" stroke-width="1.5"/><text x="40" y="46" text-anchor="middle" font-size="7" fill="#666" font-weight="bold">REF</text><circle cx="100" cy="20" r="7" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="3,2"/><circle cx="140" cy="20" r="7" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="3,2"/><circle cx="180" cy="20" r="7" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="3,2"/><text x="100" y="46" text-anchor="middle" font-size="6" fill="#999">A</text><text x="140" y="46" text-anchor="middle" font-size="6" fill="#999">B</text><text x="180" y="46" text-anchor="middle" font-size="6" fill="#999">C</text></svg></div>'

GEN_MAP = {
    "classification": class_block, "comparison": comp_block, "matching": match_block,
    "vocabulary": vocab_block, "shapes": shape_block, "counting": count_block,
    "logical reasoning": logic_block, "logical": logic_block,
}

def generate_question_blocks(data):
    qtype = safe(data.get("question_type")).lower().strip()
    for key, fn in GEN_MAP.items():
        if key in qtype:
            return fn(data)
    return ""

def build_html():
    with open(DATA_DIR / "batch_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sections = {}
    section_order = []
    for entry in manifest["batch"]:
        folder = entry["file"].rsplit(".", 1)[0]
        jp = DATA_DIR / folder / f"{folder}_result.json"
        if not jp.exists(): continue
        with open(jp, "r", encoding="utf-8") as f:
            data = json.load(f)
        qtype = safe(data.get("question_type"))
        if qtype not in sections:
            sections[qtype] = []
            section_order.append(qtype)
        heading = safe(data.get("question_heading"))
        if heading in ("None visible", "None"): heading = ""
        inst = build_instruction(data)
        blocks = generate_question_blocks(data)
        sections[qtype].append((len(sections[qtype]) + 1, heading, inst, blocks, qtype))

    cards = []
    sec_no = 1
    total_q = sum(len(v) for v in sections.values())

    for sec_name in section_order:
        items = sections[sec_name]
        cards.append('<div class="section-break"><span class="sec-label">Section ' + chr(64+sec_no) + '</span> <span class="sec-name">' + sec_name + '</span></div>')
        sec_no += 1
        for idx, heading, inst, blocks, _ in items:
            inst_html = '<div class="q-text">' + escape(inst) + '</div>' if inst else ""
            blocks_html = blocks if blocks else ""
            cards.append('<div class="qblock"><div class="qnum">' + str(idx) + '.</div>' + inst_html + blocks_html + '</div>')

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Question Paper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Times New Roman',Times,serif;background:#eef1f5;padding:30px 20px;}
.page{max-width:210mm;margin:0 auto;background:#fff;padding:20mm 25mm;min-height:297mm;box-shadow:0 2px 16px rgba(0,0,0,0.08);}
.header-bar{border-bottom:3px solid #000;padding-bottom:14px;margin-bottom:16px;}
.school{font-size:18px;font-weight:700;text-align:center;letter-spacing:1px;text-transform:uppercase;}
.subtitle{text-align:center;font-size:13px;color:#444;margin-top:2px;}
.exam-info{display:flex;justify-content:space-between;font-size:13px;margin:12px 0 0 0;font-weight:600;}
.gen-inst{margin:14px 0 18px 0;padding:10px 14px;border:1.5px solid #000;}
.gen-inst h3{font-size:13px;margin-bottom:6px;text-transform:uppercase;}
.gen-inst p{font-size:12px;line-height:1.6;color:#222;}
.section-break{margin:22px 0 12px 0;padding:6px 0;border-bottom:2px solid #000;font-size:14px;font-weight:700;text-transform:uppercase;}
.section-break .sec-label{background:#000;color:#fff;padding:2px 10px;margin-right:8px;font-size:12px;}
.section-break .sec-name{letter-spacing:0.5px;}
.qblock{margin-bottom:20px;page-break-inside:avoid;}
.qnum{font-size:14px;font-weight:700;margin-bottom:4px;}
.q-text{font-size:13.5px;line-height:1.55;color:#222;margin:4px 0 10px 18px;padding-left:10px;border-left:2.5px solid #444;}
.class-table{width:100%;border-collapse:collapse;margin:4px 0;}
.class-table td{width:50%;vertical-align:top;text-align:center;padding:8px;border:1px solid #aaa;}
.class-head{font-size:15px;font-weight:700;padding:4px 8px;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #000;}
.class-items{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;}
.citem{display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 10px;border:1px solid #ccc;min-width:55px;background:#fafafa;}
.clabel{font-size:10px;color:#333;}
.compare-table{width:100%;border-collapse:collapse;margin:4px 0;}
.compare-table td{text-align:center;padding:10px 8px;border:1px solid #ccc;}
.cpair{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;}
.vslabel{font-size:11px;color:#666;font-style:italic;}
.label-inline{font-size:10px;color:#444;}
.opp-table{width:100%;border-collapse:collapse;margin:4px 0;}
.opp-table td{padding:8px 6px;border:1px solid #ccc;vertical-align:middle;text-align:center;}
.opp-num{width:30px;font-weight:700;font-size:13px;}
.opp-img{min-width:60px;}
.opp-label{font-size:12px;font-weight:700;}
.opp-or{font-size:11px;color:#888;font-style:italic;}
.opp-choice{border:1.5px dashed #aaa;padding:6px 8px;font-size:11px;min-width:50px;}
.opp-choice.faded{opacity:0.4;}
.opp-choice span{font-size:10px;color:#555;}
.key-table{width:auto;margin:4px auto;border-collapse:collapse;}
.key-table td{padding:6px 14px;border:1px solid #ccc;text-align:center;}
.kswatch{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;}
.klabel{font-size:10.5px;color:#333;}
.figure-box{text-align:center;margin:8px 0;padding:8px;border:1px solid #ccc;background:#fafafa;}
.count-table{width:100%;border-collapse:collapse;margin:4px 0;}
.count-table td{text-align:center;padding:12px 10px;border:1px solid #ccc;width:33.33%;}
.fruits{display:flex;flex-wrap:wrap;gap:4px;justify-content:center;min-height:36px;align-items:center;}
.qmark{margin-top:6px;font-size:16px;font-weight:700;}
.stick-table{width:100%;border-collapse:collapse;margin:4px 0;}
.stick-table td{text-align:center;padding:10px;border:1px solid #ccc;vertical-align:top;}
.scol{display:flex;flex-direction:column;align-items:center;gap:6px;}
.sref{border:2px solid #888;padding:6px 12px;background:#f5f5f5;margin-bottom:4px;}
.sopts{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;}
.sopts>*{padding:3px 6px;border:1.5px dashed #aaa;}
.match-table{width:auto;margin:4px auto;border-collapse:collapse;}
.match-table td{padding:8px 16px;vertical-align:middle;text-align:center;}
.mcol{display:flex;flex-direction:column;gap:10px;}
.mitem{display:flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid #ccc;background:#fafafa;font-size:12px;}
.mdot{width:10px;height:10px;border-radius:50%;border:1.5px solid #888;display:inline-block;flex-shrink:0;}
.marr{padding:0 8px;}
.mblank{display:inline-block;width:22px;height:22px;border:1.5px dashed #aaa;border-radius:2px;flex-shrink:0;}
@media print{body{background:#fff;padding:0;}.page{box-shadow:none;padding:0.6in;}.qblock{break-inside:avoid;page-break-inside:avoid;}}
</style>
</head>
<body>
<div class="page">
  <div class="header-bar">
    <div class="school">Sunrise Public School</div>
    <div class="subtitle">Early Learning Assessment \u2014 Kindergarten</div>
    <div class="exam-info">
      <span>Time Allowed: 1 Hour</span>
      <span>Max. Marks: ''' + str(total_q) + '''</span>
    </div>
  </div>
  <div class="gen-inst">
    <h3>General Instructions</h3>
    <p>1. Read each question carefully before answering.<br>
       2. Use a pencil to write, draw, or circle your answers.<br>
       3. There are a total of ''' + str(total_q) + ''' questions across ''' + str(len(sections)) + ''' sections.</p>
  </div>
  ''' + "".join(cards) + '''
</div>
</body>
</html>'''

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("Question paper generated:", OUTPUT_HTML)
    print("Total questions:", total_q)
    for s in section_order:
        print(" ", s + ":", len(sections[s]), "questions")

if __name__ == "__main__":
    build_html()

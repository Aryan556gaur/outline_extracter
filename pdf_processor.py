import fitz  # PyMuPDF
import json
import re
import os
from collections import Counter, defaultdict
from statistics import mean


def clean_text(text):
    text = re.sub(r'-\s+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.rstrip(':.')


def merge_close_lines(lines, y_threshold=5):
    if not lines:
        return []
    merged = []
    prev = lines[0]
    for curr in lines[1:]:
        if abs(prev['bbox'][1] - curr['bbox'][1]) <= y_threshold and abs(prev['size'] - curr['size']) <= 0.5:
            prev['text'] += ' ' + curr['text']
            prev['bbox'] = (
                prev['bbox'][0], min(prev['bbox'][1], curr['bbox'][1]),
                prev['bbox'][2], max(prev['bbox'][3], curr['bbox'][3])
            )
        else:
            merged.append(prev)
            prev = curr
    merged.append(prev)
    return merged


def get_document_lines(doc):
    all_lines = []
    text_count = defaultdict(int)
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        blocks = page.get_text("dict").get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            raw_lines = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = clean_text("".join(span.get("text", "") for span in spans))
                if not line_text or len(line_text) < 3:
                    continue
                sizes = [s.get("size", 12) for s in spans if s.get("text", "").strip()]
                fonts = [s.get("font", "").lower() for s in spans if s.get("text", "").strip()]
                if not sizes:
                    continue
                avg_size = mean(sizes)
                is_bold = any("bold" in font for font in fonts)
                raw_lines.append({
                    "text": line_text,
                    "size": avg_size,
                    "bold": is_bold,
                    "page": page_num,
                    "bbox": line.get("bbox", (0, 0, 0, 0)),
                    "page_height": page_height
                })
                text_count[line_text.lower()] += 1
            merged = merge_close_lines(raw_lines)
            all_lines.extend(merged)
    return all_lines


def extract_title_from_layout(lines):
    first_page_lines = sorted([l for l in lines if l["page"] == 0], key=lambda x: x["bbox"][1])
    if not first_page_lines:
        return ""
    page_height = first_page_lines[-1]["bbox"][3]
    top_section = [l for l in first_page_lines if l["bbox"][1] < page_height * 0.25]
    if not top_section:
        top_section = first_page_lines[:min(5, len(first_page_lines))]
    max_size = max(l["size"] for l in top_section)
    candidates = [l for l in top_section if l["size"] >= max_size * 0.9]
    candidates.sort(key=lambda x: (not x["bold"], abs(x["bbox"][0] + x["bbox"][2] - 595) / 2))
    return candidates[0]["text"] if candidates else ""


def get_base_font_style(lines):
    paragraph_sizes = [round(l["size"]) for l in lines if len(l["text"]) > 150]
    if paragraph_sizes:
        base_size = Counter(paragraph_sizes).most_common(1)[0][0]
    else:
        all_sizes = [round(l["size"]) for l in lines]
        base_size = Counter(all_sizes).most_common(1)[0][0] if all_sizes else 12
    return base_size


def is_probably_noise(line, text_counts):
    text = line["text"].strip()
    lowered = text.lower()
    if len(text) < 5 or text_counts[lowered] > 2:
        return True
    if re.match(r".*@.*\\..*", text):
        return True
    if re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", text):
        return True
    if re.search(r"\b\d{5}(?:[-\s]\d{4})?\b", text):
        return True
    if re.search(r"\b(?:Street|St\.|Road|Rd\.|Parkway|Suite|Avenue)\b", text, re.IGNORECASE):
        return True
    if re.search(r"(?:\b\w(?:\s|[:;.])+){4,}", text):
        return True
    if re.search(r"(RFP:\s*R\s+){2,}", text, re.IGNORECASE):
        return True
    if len(text.split()) <= 4 and all(w.isupper() and not any(c.isdigit() for c in w) for w in text.split()):
        return True
    if any(nk in lowered for nk in ["overview", "email", "date", "rsvp", "address", "version", "waiver", "phone", "fax"]):
        return True
    if any(kw in lowered for kw in ["s.no", "name", "age", "relationship", "dob", "gender"]):
        return True
    if text.count(" ") == 0 and text.isupper() and len(text) <= 20:
        return True
    return False


def is_likely_heading(line, base_size, text_counts):
    text = line["text"].strip()
    if not re.search(r'[a-zA-Z]', text):
        return False
    if len(text.split()) < 2 or len(text) > 150:
        return False
    if is_probably_noise(line, text_counts):
        return False
    if line["size"] > base_size * 1.2 or line["bold"]:
        return True
    return False


def cleanup_outline(outline):
    cleaned = []
    max_levels = [0, 0, 0]
    seen = set()
    for item in outline:
        key = (item["level"], item["text"].lower(), item["page"])
        if key in seen:
            continue
        seen.add(key)
        level = int(item["level"][1:])
        if level == 1:
            max_levels = [len(cleaned), 0, 0]
        elif level == 2:
            if max_levels[0] == 0:
                item["level"] = "H1"
                max_levels = [len(cleaned), 0, 0]
            else:
                max_levels[1] = len(cleaned)
                max_levels[2] = 0
        elif level == 3:
            if max_levels[1] == 0:
                item["level"] = "H2"
                if max_levels[0] == 0:
                    item["level"] = "H1"
                    max_levels = [len(cleaned), 0, 0]
                else:
                    max_levels[1] = len(cleaned)
            else:
                max_levels[2] = len(cleaned)
        cleaned.append(item)
    return cleaned


def extract_outline_from_layout(lines):
    if not lines:
        return []
    text_counts = Counter(line["text"].lower() for line in lines)
    base_size = get_base_font_style(lines)
    candidates = [line for line in lines if is_likely_heading(line, base_size, text_counts)]
    if not candidates:
        return []
    x_positions = [l["bbox"][0] for l in lines if len(l["text"]) > 100]
    base_x = mean(x_positions) if x_positions else 20
    x_stdev = stdev(x_positions) if len(x_positions) > 1 else 10
    styles = {}
    for c in candidates:
        indent_level = 0
        if c["bbox"][0] > base_x + x_stdev:
            indent_level = 1
        if c["bbox"][0] > base_x + (x_stdev * 3):
            indent_level = 2
        style_key = (round(c["size"] * 2) / 2, c["bold"], indent_level)
        styles.setdefault(style_key, []).append(c["text"])
    ranked_styles = sorted(styles.keys(), key=lambda x: (-x[0], not x[1], x[2]))
    level_map = {style: f"H{min(i + 1, 3)}" for i, style in enumerate(ranked_styles)}
    outline = []
    seen = set()
    for c in candidates:
        indent_level = 0
        if c["bbox"][0] > base_x + x_stdev:
            indent_level = 1
        if c["bbox"][0] > base_x + (x_stdev * 3):
            indent_level = 2
        style_key = (round(c["size"] * 2) / 2, c["bold"], indent_level)
        level = level_map.get(style_key)
        key = (c["text"], c["page"])
        if level and key not in seen:
            outline.append({"level": level, "text": c["text"], "page": c["page"]})
            seen.add(key)
    return cleanup_outline(outline)


def process_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        meta_title = clean_text(doc.metadata.get("title", ""))
        lines = get_document_lines(doc)
        fallback_title = extract_title_from_layout(lines)
        title = fallback_title
        if meta_title and not re.search(r"[_\\/\\-]|\.docx?$", meta_title):
            title = meta_title

        toc = doc.get_toc(simple=False)
        outline = []
        if toc and len(toc) >= 3:
            for lvl, txt, page, _ in toc:
                txt = clean_text(txt)
                if lvl <= 3 and len(txt.split()) > 1 and len(txt) < 150:
                    outline.append({"level": f"H{lvl}", "text": txt, "page": page - 1})
        if not outline or len(outline) < 3:
            outline = extract_outline_from_layout(lines)
        doc.close()
        return {"title": title, "outline": outline}
    except Exception as e:
        print(f"Error processing {os.path.basename(pdf_path)}: {e}")
        return {"title": "", "outline": []}


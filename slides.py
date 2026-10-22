import json
import re
import statistics

import pymupdf

from common import clean, cos_sim, encode, similar


BOLD_FLAG = 16


def extract_slides(pdf_path, out_path=None):
    doc = pymupdf.open(pdf_path)
    slides = [{"slide": i + 1, "text": page.get_text().strip()} for i, page in enumerate(doc)]
    empty = [s["slide"] for s in slides if not s["text"]]
    if empty:
        print(f"No text on slides {empty} (image-only, need OCR)")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(slides, f, indent=2, ensure_ascii=False)
    return slides


def slide_lines(doc):
    lines = []
    for p, page in enumerate(doc):
        height = page.rect.height
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean(" ".join(s["text"].strip() for s in spans))
                if not text:
                    continue
                lines.append({
                    "slide": p + 1,
                    "text": text,
                    "size": max(s["size"] for s in spans),
                    "bold": any(s["flags"] & BOLD_FLAG for s in spans),
                    "y": line["bbox"][1] / height,
                })
    return lines


def slide_titles(lines, top=0.3):
    titles = {}
    for l in lines:
        if l["y"] < top and l["size"] > titles.get(l["slide"], {"size": 0})["size"]:
            titles[l["slide"]] = l
    return titles


CUE_WORDS = ["important", "key", "remember", "note", "exam", "test", "warning", "caution",
             "must", "never", "always", "critical", "common mistake", "don't", "do not"]
WARNING_CUES = {"warning", "caution", "never", "common mistake", "don't", "do not"}
DEFINITION = re.compile(r"\b(is defined as|refers to|is called|means|definition)\b|^[A-Z][\w\s-]{1,40}:\s", re.I)
EQUATION = re.compile(r"[=≈≤≥∑∫√±×÷^]|\b[a-z]\s*\(\s*[a-z]\s*\)|[α-ωΑ-Ω]")
EXAMPLE_STARTS = ("e.g", "example", "for example", "ex:")

HIGH, MEDIUM = 3, 1.5


def score_lines(lines, titles):
    body_size = statistics.median(l["size"] for l in lines) if lines else 12
    points = []
    for l in lines:
        if titles.get(l["slide"]) is l:
            continue
        text, low = l["text"], l["text"].lower()
        score, reasons, kind = 0.0, [], "concept"

        if l["size"] / body_size >= 1.15:
            score += 1
            reasons.append("large font")
        if l["bold"]:
            score += 1
            reasons.append("bold")
        cues = [w for w in CUE_WORDS if re.search(rf"\b{re.escape(w)}\b", low)]
        if cues:
            score += 2
            reasons.append("cue: " + ", ".join(cues))
            if WARNING_CUES & set(cues):
                kind = "warning"
        if EQUATION.search(text):
            score += 1.5
            reasons.append("equation")
            kind = "equation"
        if DEFINITION.search(text):
            score += 1.5
            reasons.append("definition")
        if low.startswith(EXAMPLE_STARTS):
            kind = "example"
        if len(text.split()) <= 2 and not reasons:
            score -= 1
            reasons.append("fragment")

        points.append({
            "slide": l["slide"],
            "title": titles[l["slide"]]["text"] if l["slide"] in titles else "",
            "text": text,
            "type": kind,
            "score": score,
            "reasons": reasons,
        })
    return points


def add_transcript_boost(points, transcript, threshold=0.55):
    if not points or not transcript:
        return points
    sims = cos_sim(encode([p["text"] for p in points]), encode([t["text"] for t in transcript]))
    for i, p in enumerate(points):
        hits = (sims[i] >= threshold).nonzero().flatten().tolist()
        p["said_at"] = [transcript[j]["start"] for j in hits]
        if hits:
            p["score"] += 2
            p["reasons"].append(f"spoken in {len(hits)} segment(s)")
        if len(hits) >= 3:
            p["score"] += 1
    return points


def label(points):
    for p in points:
        p["importance"] = "High" if p["score"] >= HIGH else "Medium" if p["score"] >= MEDIUM else "Low"
    return points


OUTLINE_TITLE = re.compile(r"\b(outline|agenda|overview|contents|topics|today|objectives)\b", re.I)


def find_outline(points, titles, max_slide=5):
    later = [t for s, t in titles.items() if s > max_slide]
    for s in range(1, max_slide + 1):
        items = [p["text"] for p in points if p["slide"] == s]
        if not items:
            continue
        by_title = OUTLINE_TITLE.search(titles.get(s, ""))
        matches = sum(any(similar(i, t) > 0.6 for t in later) for i in items)
        if by_title or matches >= max(2, len(items) // 2):
            return s, items
    return None


def assign_sections(points, titles, outline, bonus=1):
    outline_slide, items = outline
    section_of, current = {}, None
    for s in sorted(titles):
        if s <= outline_slide:
            continue
        best = max(items, key=lambda i: similar(i, titles[s]))
        if similar(best, titles[s]) > 0.6:
            current = best
        section_of[s] = current

    kept = []
    for p in points:
        if p["slide"] == outline_slide:
            continue
        p["section"] = section_of.get(p["slide"])
        if p["section"]:
            p["score"] += bonus
            p["reasons"].append("main topic in outline")
        kept.append(p)
    return kept


def analyze_slides(pdf_path, transcript=None, verbose=True):
    lines = slide_lines(pymupdf.open(pdf_path))
    title_lines = slide_titles(lines)
    titles = {s: l["text"] for s, l in title_lines.items()}

    points = score_lines(lines, title_lines)
    outline = find_outline(points, titles)
    if outline:
        if verbose:
            print(f"Outline found on slide {outline[0]}: {outline[1]}")
        points = assign_sections(points, titles, outline)
    elif verbose:
        print("No outline found, using slide titles only")

    if transcript:
        points = add_transcript_boost(points, transcript)
    return label(points)

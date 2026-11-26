"""Bringing in what a new user already has: existing notes files and PowerPoint slides.

pptx_to_pdf: a PowerPoint becomes a plain PDF (title in a big font, bullets, tables, speaker
    notes), so the slide analysis, Analyze, Define and Organize read it exactly like PDF slides.
notes_to_html: a notes file (docx, pdf, txt, md) becomes notebook HTML, keeping headings and lists.
"""

import html
import re
from pathlib import Path

PAGE = (960, 540)  # 16:9 in points
BULLET = re.compile(r"^\s*([-*•·▪◦‣–]|\d+[.)])\s+")


def read_text(path: str) -> str:
    """Text files saved on Windows are often not UTF-8."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


# ---- PowerPoint ----

def slide_text(slide):
    """(title, [body lines], speaker notes) for one slide."""
    title_shape = slide.shapes.title
    title = title_shape.text_frame.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
    title_id = title_shape.shape_id if title_shape is not None else None
    body = []
    for shape in slide.shapes:
        if shape.shape_id == title_id:  # python-pptx returns new objects each time, so compare ids
            continue
        if shape.has_text_frame:
            for p in shape.text_frame.paragraphs:
                text = "".join(r.text for r in p.runs).strip()
                if text:
                    body.append("    " * p.level + "- " + text)  # the built-in PDF font has no •
        elif getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    body.append(" | ".join(cells))
    if not title and body:  # no title placeholder: use the first line
        title = body.pop(0).lstrip("- ").strip()
    notes = ""
    if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
        notes = slide.notes_slide.notes_text_frame.text.strip()
    return title, body, notes


# The built-in PDF font only has Latin-1, so anything else would come out as "?"
PLAIN = str.maketrans({"→": "->", "←": "<-", "⇒": "=>", "⇐": "<=", "↔": "<->", "≈": "~", "≤": "<=", "≥": ">=",
                       "≠": "!=", "−": "-", "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
                       "•": "-", "…": "...", "∑": "sum", "√": "sqrt", "∞": "inf", "∈": "in"})


def latin1(text: str) -> str:
    text = text.translate(PLAIN)
    return "".join(ch if ord(ch) < 256 else "?" for ch in text)


def fit_textbox(page, rect, text, size, min_size=8, **kw):
    """insert_textbox returns < 0 when the text doesn't fit, so shrink until it does."""
    import pymupdf
    text = latin1(text)
    while size >= min_size:
        shape = page.new_shape()
        if shape.insert_textbox(pymupdf.Rect(rect), text, fontsize=size, **kw) >= 0:
            shape.commit()
            return
        size -= 1
    page.insert_textbox(pymupdf.Rect(rect), text, fontsize=min_size, **kw)  # cut off rather than lose it all


def pptx_to_pdf(src: str, dst: str) -> int:
    """Returns the number of slides written."""
    import pymupdf
    from pptx import Presentation
    deck = Presentation(src)
    pdf = pymupdf.open()
    count = 0
    for slide in deck.slides:
        title, body, notes = slide_text(slide)
        if not (title or body or notes):
            continue
        page = pdf.new_page(width=PAGE[0], height=PAGE[1])
        if title:
            fit_textbox(page, (40, 30, 920, 110), title, 28, min_size=14, fontname="helv")
        text = "\n".join(body)
        if notes:
            text += ("\n\n" if text else "") + "Speaker notes: " + notes
        if text:
            fit_textbox(page, (40, 120, 920, 520), text, 16, fontname="helv")
        count += 1
    if not count:
        raise ValueError("The PowerPoint has no text in it.")
    pdf.save(dst)
    return count


# ---- notes files ----

def lines_to_html(lines) -> str:
    """[(kind, text)] with kind h2/h3/li/p -> HTML, grouping list items into <ul>."""
    out, in_list = [], False
    for kind, text in lines:
        if kind == "li" and not in_list:
            out.append("<ul>")
            in_list = True
        elif kind != "li" and in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<{kind}>{html.escape(text)}</{kind}>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def text_lines(text: str):
    """Plain text / markdown / PDF text -> [(kind, text)]."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            out.append(("h3", line[4:].strip()))
        elif line.startswith(("# ", "## ")):
            out.append(("h2", line.lstrip("#").strip()))
        elif BULLET.match(line):
            out.append(("li", BULLET.sub("", line).strip()))
        else:
            out.append(("p", line))
    return out


def docx_paragraph(p, out):
    text = p.text.strip()
    if not text:
        return
    style = (p.style.name if p.style is not None else "").lower()
    if style == "title" or style == "heading 1":
        out.append(("h2", text))
    elif style.startswith("heading"):
        out.append(("h3", text))
    elif "list" in style or BULLET.match(text):
        out.append(("li", BULLET.sub("", text).strip()))
    else:
        out.append(("p", text))


def docx_lines(path: str):
    """Paragraphs and tables in document order, then any text boxes (people often put notes in those)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    document = docx.Document(path)
    out = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            docx_paragraph(Paragraph(child, document), out)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells = []
                for cell in row.cells:
                    text = " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                    if text and (not cells or cells[-1] != text):  # merged cells repeat
                        cells.append(text)
                if cells:
                    out.append(("li", " | ".join(cells)))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for box in document.element.body.findall(".//w:txbxContent", ns):
        for p in box.findall(".//w:p", ns):
            docx_paragraph(Paragraph(p, document), out)
    return out


# ---- PDFs: slides and notes ----
# PDF text comes out line by line with every page's header/footer, page numbers, sentence
# wraps and equation fragments mixed in. This cleans that up before anything else sees it.

GLYPH = re.compile(r"^\s*[•·▪◦‣▶►■□➢✓\-*–]\s*")
PAGE_NO = re.compile(r"^(page\s*)?\d*\s*(/|of)\s*\d+$|^\d{1,3}$", re.I)
CHROME = re.compile(r"^current\s+(sub)*section$", re.I)  # Beamer navigation labels


def norm(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.lower())).strip()


def real_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", text))


def pdf_pages(path: str):
    """[{landscape, lines: [{text, size}]}] in reading order."""
    import pymupdf
    pages = []
    with pymupdf.open(path) as doc:
        for page in doc:
            lines = []
            for block in page.get_text("dict", sort=True)["blocks"]:
                for line in block.get("lines", []):
                    spans = [sp for sp in line["spans"] if sp["text"].strip()]
                    if not spans:
                        continue
                    text = re.sub(r"\s+", " ", " ".join(sp["text"] for sp in spans)).strip()
                    lines.append({"text": text, "size": round(max(sp["size"] for sp in spans), 1),
                                  "y": line["bbox"][1], "h": line["bbox"][3] - line["bbox"][1]})
            pages.append({"landscape": page.rect.width > page.rect.height, "lines": lines,
                          "height": page.rect.height})
    return pages


def drop_boilerplate(pages):
    """Removes text that repeats on many pages (headers, footers, nav bars) and page numbers."""
    n = len(pages)
    counts = {}
    for pg in pages:
        for key in {norm(l["text"]) for l in pg["lines"]}:
            counts[key] = counts.get(key, 0) + 1
    limit = max(3, 0.3 * n)
    size = body_size(pages)
    for pg in pages:
        # slide nav bars sit lower than a document's header, so slides get a taller zone
        z = 0.12 if pg["landscape"] else 0.08
        top, bottom = z * pg["height"], (1 - z) * pg["height"]
        keep = []
        for l in pg["lines"]:
            zone = l["y"] < top or l["y"] > bottom
            repeated = n >= 4 and counts[norm(l["text"])] >= limit
            if zone and (PAGE_NO.match(l["text"]) or l["size"] < 0.8 * size  # nav bars, page numbers
                         or (repeated and l["size"] <= size + 0.5)):         # running headers/footers
                continue
            if CHROME.match(l["text"]):
                continue
            keep.append(l)
        pg["lines"] = keep


def join_lines(lines, body_size):
    """Line-by-line PDF text -> items (bullets / paragraphs), rejoining wrapped sentences and
    dropping equation and table-cell fragments."""
    items = []
    prev = None
    for l in lines:
        text = l["text"]
        starts_item = bool(GLYPH.match(text)) and not text.startswith("-" * 2)
        same_style = prev is not None and abs(l["size"] - prev["size"]) < 0.6
        close = prev is not None and l["y"] - (prev["y"] + prev["h"]) < max(4, 0.8 * l["h"])
        ended = prev is not None and re.search(r"[.!?]$", prev["text"]) and text[:1].isupper()
        if items and not starts_item and same_style and close and not ended:
            items[-1]["text"] += " " + text
        else:
            items.append({"text": GLYPH.sub("", text).strip(), "size": l["size"], "bullet": starts_item})
        prev = l
    out = []
    for it in items:
        t = it["text"]
        if real_words(t) < 2 and not t.endswith(":"):
            continue  # "Doc2", "cat", "|xi|,", "x′" ...
        if out and out[-1]["text"].endswith(":") and real_words(out[-1]["text"]) <= 3:
            out[-1]["text"] += " " + t  # "Method:" + what follows
            continue
        out.append(it)
    return [it for it in out if real_words(it["text"]) >= 2]


def body_size(pages):
    sizes = sorted(l["size"] for pg in pages for l in pg["lines"])
    return sizes[len(sizes) // 2] if sizes else 10


def slide_items(pages):
    """Slide decks: [(title, [items])], one per slide, with Beamer's step-by-step reveal
    copies (same title, a few more bullets each time) merged into one slide."""
    size = body_size(pages)
    slides = []
    for pg in pages:
        lines = pg["lines"]
        if not lines:
            continue
        top = max(l["size"] for l in lines)
        if top >= size * 1.15:
            ti = next(i for i, l in enumerate(lines) if l["size"] == top)
        else:
            ti = 0
        title = lines[ti]["text"]
        items = join_lines(lines[:ti] + lines[ti + 1:], size)
        if slides and norm(slides[-1][0]) == norm(title):
            same = lambda t: re.sub(r"\s+", " ", t.lower()).strip()
            seen = [same(x["text"]) for x in slides[-1][1]]
            for it in items:
                k = same(it["text"])
                if not any(k == s or k.startswith(s) or s.startswith(k) for s in seen):
                    slides[-1][1].append(it)
        else:
            slides.append((title, items))
    return slides


def pdf_to_lines(path: str):
    """A PDF -> [(kind, text)]. Landscape pages are treated as slides (title + bullets),
    portrait pages as a document (headings by font size, paragraphs, bullets)."""
    pages = pdf_pages(path)
    drop_boilerplate(pages)
    if not any(pg["lines"] for pg in pages):
        return []
    if sum(pg["landscape"] for pg in pages) > len(pages) / 2:
        out = []
        for title, items in slide_items(pages):
            out.append(("h2", title[:120]))
            for it in items:
                kind = "p" if it["text"].startswith("Speaker notes:") else "li"
                out.append((kind, it["text"]))
        return out
    size = body_size(pages)
    big = sorted({l["size"] for pg in pages for l in pg["lines"] if l["size"] >= size + 2}, reverse=True)
    out = []
    for pg in pages:
        for it in join_lines(pg["lines"], size):
            if big and it["size"] >= big[0] - 0.5 and real_words(it["text"]) <= 12:
                out.append(("h2", it["text"]))
            elif it["size"] >= size + 2 and real_words(it["text"]) <= 12:
                out.append(("h3", it["text"]))
            elif it["bullet"]:
                out.append(("li", it["text"]))
            else:
                out.append(("p", it["text"]))
    return out


def slides_outline(pdf_path: str) -> tuple[str, str]:
    """Slides PDF (a converted PowerPoint or a real deck) -> a slide-by-slide outline note."""
    lines = pdf_to_lines(pdf_path)
    return lines_to_html(lines), "\n".join(t for _, t in lines)


def notes_to_html(path: str) -> tuple[str, str]:
    """-> (html for the note body, plain text). Plain text is what Organize and Analyze read."""
    low = path.lower()
    if low.endswith(".docx"):
        lines = docx_lines(path)
    elif low.endswith(".pdf"):
        lines = pdf_to_lines(path)
    else:
        lines = text_lines(read_text(path))
    return lines_to_html(lines), "\n".join(t for _, t in lines)


def title_from_filename(name: str) -> str:
    stem = Path(name or "").stem
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return (stem[:1].upper() + stem[1:])[:150] if stem else "Imported note"

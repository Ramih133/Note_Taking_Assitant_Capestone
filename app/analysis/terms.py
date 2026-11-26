"""Course page: key terms and "this will be on the exam" moments from a note's lecture transcript,
each linked back to the lines in the student's notes that cover it."""

import html
import re

# ---- reading the notes ----

BLOCK = re.compile(r"</?(p|div|li|h1|h2|h3|blockquote|br)\s*/?>", re.I)
TAG = re.compile(r"<[^>]+>")


def note_lines(body_html: str) -> list[str]:
    """Notebook note HTML -> one string per line/paragraph, empties dropped."""
    text = BLOCK.sub("\n", body_html or "")
    text = html.unescape(TAG.sub("", text))
    lines = [re.sub(r"\s+", " ", l).strip(" -*•\t") for l in text.split("\n")]
    return [l for l in lines if len(l) > 1]


# ---- finding terms and exam cues in the transcript ----

EXAM_CUES = re.compile(
    r"\b(on (the|your) (exam|test|midterm|final|quiz)"
    r"|(exam|test|midterm|final) (question|material)"
    r"|will be tested|you('ll| will) be tested|be tested on"
    r"|know this|need to know|you should know|make sure you (know|understand|remember)"
    r"|remember this|don't forget|do not forget|very important|really important|this is important"
    r"|pay attention to|write this down|take note)\b", re.I)

# "X is defined as Y", "X refers to Y", "we call this X", ...
TERM = r"([A-Za-z][\w\-']*(?:\s+[\w\-']+){0,3})"
DEF_PATTERNS = [
    re.compile(TERM + r",?\s+(?:is|are)\s+defined\s+as\s+(.+)", re.I),
    re.compile(TERM + r",?\s+(?:refers?\s+to|stands\s+for)\s+(.+)", re.I),
    re.compile(TERM + r"\s+(?:is|are)\s+(?:called|known\s+as)\s+(.+)", re.I),          # flipped below
    re.compile(r"\b(?:we|you)\s+call\s+(?:this|that|it|these|them)\s+(?:an?\s+|the\s+)?" + TERM + r"()", re.I),
    re.compile(r"\b(?:the\s+)?definition\s+of\s+" + TERM + r"\s+is\s+(.+)", re.I),
]
FILLER = {"this", "that", "it", "which", "what", "there", "here", "they", "these", "those", "so", "and",
          "the", "a", "an", "um", "uh", "basically", "okay", "now", "well"}


def sentences(lines: list[dict]) -> list[tuple[str, str]]:
    """Transcript lines ({stamp, text}) -> (stamp, sentence)."""
    out = []
    for line in lines:
        for s in re.split(r"(?<=[.!?])\s+", line.get("text", "")):
            if s.strip():
                out.append((line.get("stamp", ""), s.strip()))
    return out


def clean_term(t: str) -> str:
    words = t.strip(" ,.;:\"'").split()
    while words and words[0].lower() in FILLER:   # "so the gradient" -> "gradient"
        words.pop(0)
    return " ".join(words)


def find_definitions(sents: list[tuple[str, str]]) -> list[dict]:
    found = {}
    for i, (stamp, s) in enumerate(sents):
        for n, pat in enumerate(DEF_PATTERNS):
            m = pat.search(s)
            if not m:
                continue
            term, definition = m.group(1), m.group(2)
            if n == 2:                       # "the slope is called the gradient": term is on the right
                term, definition = definition, term
            if n == 3:                       # "we call this X": the definition is the sentence before
                definition = sents[i - 1][1] if i else ""
            term = clean_term(re.split(r"[,.;:]", term)[0])
            if not term or len(term) < 3 or len(term.split()) > 4 or term.lower() in FILLER:
                continue
            key = term.lower()
            if key not in found:
                found[key] = {"kind": "term", "term": term,
                              "detail": definition.strip()[:400], "stamp": stamp}
            break
    return list(found.values())


def find_exam_cues(sents: list[tuple[str, str]]) -> list[dict]:
    """Each cue keeps the sentence before and after, since the prof often says the point
    first and "that'll be on the exam" second (or the other way around)."""
    out, last = [], -3
    for i, (stamp, s) in enumerate(sents):
        if not EXAM_CUES.search(s) or i - last < 2:   # skip repeats of the same moment
            continue
        last = i
        context = " ".join(t for _, t in sents[max(0, i - 1): i + 2])
        out.append({"kind": "exam", "term": s[:200], "detail": context[:600], "stamp": stamp})
    return out


# Real lectures rarely say "X is defined as", so the local LLM (same Qwen as quizzes/Define)
# picks the key terms from each ~150-word window. Every term it returns has to appear word for
# word in that window, so it can't invent terms. The patterns above still run as a backup.

WINDOW_WORDS = 150
TERMS_PER_WINDOW = 3

LLM_PROMPT = """From this lecture excerpt, list up to {n} key terms a student should know for the exam:
technical terms, named concepts, important people or events. Skip filler and jokes.
Copy each term exactly as it appears in the excerpt (1-4 words).
Give a one-sentence definition based on the excerpt.
Answer with JSON only: [{{"term": "...", "definition": "..."}}]

Excerpt:
{text}"""


def windows(sents: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """(stamp of first sentence, text) chunks of about WINDOW_WORDS words."""
    out, buf, words, start = [], [], 0, None
    for stamp, s in sents:
        if start is None:
            start = stamp
        buf.append(s)
        words += len(s.split())
        if words >= WINDOW_WORDS:
            out.append((start, " ".join(buf)))
            buf, words, start = [], 0, None
    if buf and (words >= 30 or not out):  # skip a tiny tail, unless it's the whole lecture
        out.append((start, " ".join(buf)))
    return out


def parse_llm_terms(reply: str, window_text: str) -> list[tuple[str, str]]:
    """Pull (term, definition) pairs out of the model's reply. Drops anything not in the window."""
    import json
    m = re.search(r"\[.*\]", reply or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    low = window_text.lower()
    out = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict):
            continue
        term = clean_term(str(d.get("term", "")))
        definition = re.sub(r"\s+", " ", str(d.get("definition", ""))).strip()
        if 2 < len(term) <= 60 and len(term.split()) <= 4 and term.lower() in low and term.lower() not in FILLER:
            out.append((term, definition[:300]))
    return out[:TERMS_PER_WINDOW]


def find_terms_llm(sents: list[tuple[str, str]], generate) -> list[dict]:
    found = {}
    for stamp, text in windows(sents):
        msgs = [{"role": "user", "content": LLM_PROMPT.format(n=TERMS_PER_WINDOW, text=text)}]
        try:
            reply = generate(msgs, 220)
        except Exception:
            continue
        for term, definition in parse_llm_terms(reply, text):
            found.setdefault(term.lower(), {"kind": "term", "term": term, "detail": definition, "stamp": stamp})
    return list(found.values())


def get_llm():
    try:
        from analysis.quiz_llm import llm_available, get_generator
        return get_generator() if llm_available() else None
    except Exception:
        return None


def extract(transcript_lines: list[dict], generate="auto") -> list[dict]:
    sents = sentences(transcript_lines)
    terms = {t["term"].lower(): t for t in find_definitions(sents)}  # explicit definitions win
    if generate == "auto":
        generate = get_llm()
    if generate is not None:
        for t in find_terms_llm(sents, generate):
            terms.setdefault(t["term"].lower(), t)
    return list(terms.values()) + find_exam_cues(sents)


# ---- linking to the notes ----

LINK_MIN = 0.45   # same threshold the live gap check uses; tune on real notes
MAX_REFS = 3


def exact_hit(term: str, line: str) -> bool:
    """Whole-word, case-insensitive, allows a plural s/es."""
    pat = r"\b" + r"\s+".join(re.escape(w) for w in term.lower().split()) + r"(e?s)?\b"
    return re.search(pat, line.lower()) is not None


def link(items: list[dict], notes: list[tuple[int, list[str]]], encode=None) -> list[list[dict]]:
    """For each item, the note lines that cover it: [{note_id, line_idx, snippet, score}, ...].
    notes = [(note_id, lines)]. encode(texts) -> L2-normalised numpy array (defaults to the matcher)."""
    flat = [(nid, i, line) for nid, lines in notes for i, line in enumerate(lines)]
    if not items or not flat:
        return [[] for _ in items]
    if encode is None:
        encode = default_encode
    queries = [f"{it['term']}: {it['detail']}" if it["kind"] == "term" else it["detail"] for it in items]
    q = encode(queries)
    n = encode([line for _, _, line in flat])
    sims = q @ n.T

    out = []
    for k, it in enumerate(items):
        scored = []
        for j, (nid, i, line) in enumerate(flat):
            score = float(sims[k, j])
            exact = it["kind"] == "term" and exact_hit(it["term"], line)
            # short terms ("loss", "bias") match everywhere, so a word match alone isn't enough for them
            if exact and (len(it["term"]) > 5 or score >= LINK_MIN - 0.15):
                score = max(score, 0.99)
            if score >= LINK_MIN:
                scored.append({"note_id": nid, "line_idx": i, "snippet": line[:160], "score": round(score, 3)})
        scored.sort(key=lambda r: -r["score"])
        out.append(scored[:MAX_REFS])
    return out


def default_encode(texts):
    from analysis.common import get_model
    return get_model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)

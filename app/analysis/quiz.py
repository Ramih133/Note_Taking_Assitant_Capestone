import json
import re

# Turns missed slide points into practice cards. No model needed.
# "X is Y" / "X: Y" style points become definition questions,
# everything else becomes fill-in-the-blank on its most specific word.

# Lecture filler words on top of the standard English list
LECTURE_STOPWORDS = {
    "slide", "slides", "lecture", "example", "examples", "important", "note", "notes",
    "remember", "today", "week", "class", "chapter", "section", "basically", "really",
}

try:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
    STOPWORDS = frozenset(ENGLISH_STOP_WORDS) | LECTURE_STOPWORDS
except ImportError:  # scikit-learn comes with sentence-transformers, but just in case
    TfidfVectorizer = None
    STOPWORDS = frozenset(LECTURE_STOPWORDS | {
        "about", "after", "because", "before", "being", "between", "could", "during", "every",
        "from", "have", "into", "more", "most", "much", "other", "should", "some", "such", "than",
        "that", "their", "them", "then", "there", "these", "they", "this", "those", "through",
        "under", "used", "using", "very", "what", "when", "where", "which", "while", "will",
        "with", "would", "your", "always", "never"})

WORD = r"[A-Za-z][A-Za-z0-9\-']{3,}"


def word_weights(texts):
    """TF-IDF over all the lecture's points: a word scores high when it matters in its own point
    but is rare across the lecture. Returns one {word: score} dict per text."""
    if TfidfVectorizer is None or not texts:
        return [{} for _ in texts]
    try:
        vec = TfidfVectorizer(token_pattern=WORD, lowercase=True, stop_words=list(STOPWORDS))
        matrix = vec.fit_transform(texts)
    except ValueError:  # every word was a stopword
        return [{} for _ in texts]
    vocab = vec.get_feature_names_out()
    weights = []
    for row in matrix:
        row = row.tocoo()
        weights.append({vocab[j]: v for j, v in zip(row.col, row.data)})
    return weights


DEFINITION = re.compile(
    # no dashes: they're used for date ranges ("500 – 1500 CE") far more than definitions
    r"^(?P<term>[^.?!:]{2,60}?)\s*(?P<sep>:| is | are | refers to | means )\s*(?P<body>.{8,})$",
    re.IGNORECASE,
)


def clean(text):
    text = re.sub(r"^[\s•\-\*•\d.)]+", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def balanced(s):
    return s.count("(") == s.count(")") and s.count("[") == s.count("]")


def definition_card(text, section=""):
    m = DEFINITION.match(text)
    if not m:
        return None
    term, sep, body = m["term"].strip(), m["sep"].strip().lower(), m["body"].strip()
    # a split in the middle of brackets, or an "answer" that's just a number/date, isn't a definition
    if not (balanced(term) and balanced(body)) or body[0].isdigit() or len(body.split()) < 3:
        return None
    # "Privateers: Francis Drake, Henry Morgan" is a list of examples, not a definition
    parts = [p.strip() for p in re.split(r",|;| and ", body) if p.strip()]
    if len(parts) >= 2 and all(len(p.split()) <= 3 for p in parts):
        return None
    # skip things like "This is ..." or "It means ..." where the "term" isn't a real term
    if len(term.split()) > 6 or term.lower() in {"this", "it", "that", "there", "here", "which"}:
        return None
    # "Learning rates that are too high..." isn't a definition, it's a clause
    clause_words = {"that", "which", "who", "when", "where", "if", "because", "so", "too", "not"}
    if clause_words & {w.lower() for w in term.split()}:
        return None
    # add the section so a bare "Define: X" has context
    context = f" (in {section})" if section and section.lower() not in term.lower() else ""
    question = {
        "is": f"What is {term}{context}?",
        "are": f"What are {term}{context}?",
        "refers to": f"What does {term} refer to{context}?",
        "means": f"What does {term} mean{context}?",
    }.get(sep, f"Define: {term}{context}")
    return question, body[0].upper() + body[1:]


def pick_blank(text, section="", weights=None):
    words = re.findall(WORD, text)
    candidates = [w for w in words if w.lower() not in STOPWORDS]
    if not candidates:
        return None
    weights = weights or {}
    section_words = {w.lower() for w in re.findall(r"\w+", section or "")}

    def rank(w):
        score = weights.get(w.lower(), 0.0)          # TF-IDF: key to this point, rare elsewhere
        if w.lower() in section_words:
            score += 0.1                             # it's what the section is about
        if w[0].isupper() or any(c.isupper() for c in w[1:]) or "-" in w:
            score += 0.15                            # names / technical terms
        return (score, len(w))

    return max(candidates, key=rank)


def cloze_card(text, section="", weights=None):
    word = pick_blank(text, section, weights)
    if not word or len(text.split()) < 4:
        return None
    blanked = re.sub(rf"\b{re.escape(word)}\b", "_____", text, count=1)
    return f"Fill in the blank: {blanked}", f"{word}. Full point: {text}"


def make_cards(points):
    cards, seen = [], set()
    texts = [clean(p.get("text")) for p in points]
    all_weights = word_weights(texts)
    for point, text, weights in zip(points, texts, all_weights):
        if not text:
            continue
        section = point.get("section") or point.get("title") or ""
        card = definition_card(text, section) or cloze_card(text, section, weights)
        if card is None:  # too short to make a real question out of
            continue
        question, answer = card
        if question.lower() in seen:
            continue
        seen.add(question.lower())
        if point.get("slide") is not None:
            answer += f" (slide {point['slide']})"
        cards.append((question[:500], answer[:2000]))
    return cards


# --- Multiple choice ---------------------------------------------------------
# Works out the short "correct option" for a card from its question/answer,
# so cards made before this existed (and hand-written ones) still work.

SLIDE_TAG = re.compile(r"\s*\(slide \d+\)$")


def card_parts(question, answer):
    answer = answer or ""
    if question.startswith("Fill in the blank:"):
        return "cloze", answer.split(". Full point:")[0].strip()
    if re.match(r"^(What (is|are|does)|Define:)", question):
        return "definition", SLIDE_TAG.sub("", answer).strip()
    return "manual", SLIDE_TAG.sub("", answer).strip()


def keywords(text):
    text = SLIDE_TAG.sub("", (text or "").split("Full point:")[-1])  # skip the answer's own labels
    words = re.findall(WORD, text)
    return [w for w in words if w.lower() not in STOPWORDS]


def stored_options(card):
    try:
        options = json.loads(card.get("options") or "[]")
    except (TypeError, ValueError):
        return None
    if len(options) >= 2 and isinstance(card.get("correct"), int) and 0 <= card["correct"] < len(options):
        return options
    return None


def choice_of(card):
    options = stored_options(card)
    if options:
        return "ai", options[card["correct"]]
    return card_parts(card["question"], card["answer"])


def build_question(card, pool, rng, n_options=4):
    """card: dict with id/question/answer(/options/correct). pool: other cards to steal wrong answers from."""
    options = stored_options(card)
    if options:  # AI-written: already has its own wrong answers
        correct = options[card["correct"]]
        options = options[:]
        rng.shuffle(options)
        return {"id": card["id"], "type": "choice", "question": card["question"], "options": options,
                "correct": options.index(correct), "answer": card["answer"], "made_by": describe_source(card)}

    kind, correct = card_parts(card["question"], card["answer"])
    taken = {correct.lower()}
    distractors = []

    def take(option):
        option = (option or "").strip().rstrip(",;:")
        if not balanced(option):
            return
        if option and option.lower() not in taken and len(distractors) < n_options - 1:
            taken.add(option.lower())
            distractors.append(option)

    others = [choice_of(c) for c in pool if c["id"] != card["id"]]
    rng.shuffle(others)
    for other_kind, other_choice in others:
        if other_kind == kind:
            take(other_choice)
    if kind == "cloze":
        # not enough other blanks: use key terms from the rest of the course material
        words = [w for c in pool if c["id"] != card["id"] for w in keywords(c["answer"])]
        rng.shuffle(words)
        for w in words:
            take(w)
    else:
        for other_kind, other_choice in others:
            if other_kind != "cloze":
                take(other_choice)

    if len(distractors) < 1:
        # can't make a fair multiple choice, so fall back to a flip card
        return {"id": card["id"], "type": "flip", "question": card["question"], "answer": card["answer"],
                "made_by": describe_source(card)}
    options = distractors + [correct]
    rng.shuffle(options)
    made_by = describe_source(card)
    if card.get("source") != "manual":
        made_by += "; wrong answers taken from your other cards"
    return {"id": card["id"], "type": "choice", "question": card["question"], "options": options,
            "correct": options.index(correct), "answer": card["answer"], "made_by": made_by}


def describe_source(card):
    """Short label for the quiz page saying how this question was made."""
    source, method = card.get("source") or "manual", card.get("method") or ""
    if source == "manual":
        return "Written by you"
    if source == "ai":
        return f"AI-written ({method})" if method else "AI-written"
    kind, _ = card_parts(card["question"], card["answer"])
    label = {
        "definition": "Auto: definition pattern in the slide text",
        "cloze": "Auto: fill-in-the-blank, key term picked by TF-IDF",
    }.get(kind, "Auto-generated")
    if method == "fallback":
        label += " (AI output for this section wasn't usable)"
    return label
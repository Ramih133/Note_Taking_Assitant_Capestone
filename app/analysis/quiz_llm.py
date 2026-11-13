import json
import logging
import os
import re
import threading

# Writes multiple-choice questions with a local LLM, one lecture section at a time.
# Any section where the model gives back junk falls back to the rule-based cards in quiz.py,
# so a quiz always gets made.
#
# Change the model without touching code:   set QUIZ_LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
# Bigger = better questions but slower. 1.5B runs OK on CPU, 3B+ really wants a GPU.

MODEL_NAME = os.environ.get("QUIZ_LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
QUESTIONS_PER_SECTION = 3
MAX_SECTIONS = 8

_generator = None
_lock = threading.Lock()
_run_lock = threading.Lock()  # one generation at a time; the model isn't safe to share across threads


def get_generator():
    """Load the model once and keep it in memory. Returns a function (messages, max_new_tokens) -> text.
    Shared by the quiz and the notes Define button."""
    global _generator
    with _lock:
        if _generator is None:
            from transformers import pipeline
            pipe = pipeline("text-generation", model=MODEL_NAME, torch_dtype="auto", device_map="auto")

            def generate(messages, max_new_tokens=900):
                with _run_lock:
                    out = pipe(messages, max_new_tokens=max_new_tokens, do_sample=False, return_full_text=False)
                return out[0]["generated_text"]

            _generator = generate
    return _generator


def llm_available():
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


SYSTEM_PROMPT = """You write multiple-choice quiz questions for a university student reviewing a lecture.
Rules:
- Use ONLY the lecture material given. Do not add outside facts.
- Each question has exactly 4 options. Exactly one is correct.
- Wrong options must be plausible to someone who skimmed the lecture, not silly.
- Mix question styles: definitions, "why", "which of these", applying a concept.
- Keep options short (under 15 words each). Don't use "all of the above" or "none of the above".
- Reply with ONLY a JSON array, no other text:
[{"question": "...", "options": ["...", "...", "...", "..."], "correct": 0, "explanation": "one sentence"}]"""


def build_prompt(section, points, n):
    lines = []
    for p in points:
        flag = " (student MISSED this in their notes)" if p.get("missed") else ""
        lines.append(f"- {p['text']}{flag}")
    focus = ("Focus at least one question on the points the student missed.\n"
             if any(p.get("missed") for p in points) else "")
    user = (f"Lecture section: {section}\n\nMaterial:\n" + "\n".join(lines) +
            f"\n\n{focus}Write {n} questions.")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_questions(text):
    """Pull a JSON array out of model output and keep only questions that are actually usable."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    raw = re.sub(r",\s*([\]}])", r"\1", text[start:end + 1])  # small models love trailing commas
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []

    good = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options")
        correct = item.get("correct")
        if not question or not isinstance(options, list) or len(options) != 4:
            continue
        options = [re.sub(r"^\s*[A-Da-d1-4][.)]\s+", "", str(o)).strip() for o in options]
        if any(not o for o in options) or len({o.lower() for o in options}) != 4:
            continue
        if isinstance(correct, str):  # sometimes it gives "B" or the answer text instead of an index
            c = correct.strip()
            if len(c) == 1 and c.upper() in "ABCD":
                correct = "ABCD".index(c.upper())
            elif c.isdigit():
                correct = int(c)
            else:
                correct = next((i for i, o in enumerate(options) if o.lower() == c.lower()), None)
        if not isinstance(correct, int) or not 0 <= correct < 4:
            continue
        if any(bad in " ".join(options).lower() for bad in ("all of the above", "none of the above")):
            continue
        good.append({
            "question": question[:500],
            "options": [o[:300] for o in options],
            "correct": correct,
            "explanation": str(item.get("explanation", "")).strip()[:1000],
        })
    return good


def group_by_section(points):
    sections = {}
    for p in points:
        text = (p.get("text") or "").strip()
        if len(text.split()) < 3:
            continue
        name = p.get("section") or p.get("title") or (f"Slide {p['slide']}" if p.get("slide") else "Lecture")
        sections.setdefault(name, []).append(p)
    # sections with missed points first, then by how much material they have
    return sorted(sections.items(), key=lambda kv: (not any(p.get("missed") for p in kv[1]), -len(kv[1])))


def make_llm_cards(points, generate=None):
    """points: dicts with text/section/slide, missed points marked with missed=True.
    Returns (cards, used_llm_sections, fallback_sections). Each card is a dict ready for the database."""
    from analysis.quiz import make_cards

    generate = generate or get_generator()
    cards, llm_sections, fallback_sections = [], 0, 0
    for section, section_points in group_by_section(points)[:MAX_SECTIONS]:
        questions = []
        try:
            questions = parse_questions(generate(build_prompt(section, section_points[:15], QUESTIONS_PER_SECTION)))
        except Exception:
            logging.exception("LLM failed on section %s", section)
        slides = sorted({p["slide"] for p in section_points if p.get("slide") is not None})
        where = f" (slide {slides[0]})" if len(slides) == 1 else f" (slides {slides[0]}-{slides[-1]})" if slides else ""
        if questions:
            llm_sections += 1
            for q in questions[:QUESTIONS_PER_SECTION]:
                correct_text = q["options"][q["correct"]]
                cards.append({
                    "question": q["question"],
                    "answer": f"{correct_text}. {q['explanation']}{where}".strip(),
                    "options": json.dumps(q["options"]),
                    "correct": q["correct"],
                    "method": MODEL_NAME,
                })
        else:
            fallback_sections += 1
            for question, answer in make_cards(section_points)[:QUESTIONS_PER_SECTION]:
                cards.append({"question": question, "answer": answer, "options": "", "correct": None,
                              "method": "fallback"})
    return cards, llm_sections, fallback_sections
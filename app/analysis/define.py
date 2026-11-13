import re

# Powers the Define button on the lecture notes page.
# Finds where the highlighted term shows up in the lecture (slides, transcript, lecture text)
# and has the local LLM define / explain / give an example, grounded in that context.

MODES = {
    # mode: (instruction, max_new_tokens)
    "define": ("Give a short definition of the term in 1-2 sentences.", 120),
    "explain": ("Explain the term in more depth in one short paragraph (4-6 sentences). "
                "Build on the definition already given; don't just repeat it.", 320),
    "example": ("Give one concrete, specific example of the term in 2-4 sentences. "
                "If the lecture has an example, use that one.", 260),
}

SYSTEM_PROMPT = """You help a university student understand terms while they take lecture notes.
- If lecture excerpts are given and they use the term, base your answer on how the lecture uses it.
- If the excerpts don't cover it, answer from general knowledge.
- Plain text only. No preamble like "Sure!" or "Here is". No markdown, no bullet points."""

MAX_SNIPPETS = 6


def split_sentences(text):
    text = re.sub(r"\s+", " ", text or "")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\s•\s", text) if len(s.strip()) > 15]


def find_context(term, sentences):
    """Lecture sentences that mention the term. Falls back to its individual words for multi-word terms."""
    term_l = term.lower()
    hits = [s for s in sentences if term_l in s.lower()]
    if not hits:
        words = [w for w in re.findall(r"[a-z0-9\-']{4,}", term_l)]
        if len(words) > 1:
            scored = [(sum(w in s.lower() for w in words), s) for s in sentences]
            hits = [s for score, s in sorted(scored, key=lambda x: -x[0]) if score >= max(2, len(words) - 1)]
    seen, out = set(), []
    for s in hits:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s[:300])
        if len(out) == MAX_SNIPPETS:
            break
    return out


def build_messages(term, mode, context, previous=""):
    instruction, _ = MODES[mode]
    parts = [f'Term: "{term}"']
    if context:
        parts.append("Lecture excerpts:\n" + "\n".join(f"- {c}" for c in context))
    else:
        parts.append("(The lecture material doesn't mention this term.)")
    if previous:
        parts.append(f"Definition already given to the student: {previous}")
    parts.append(instruction)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n\n".join(parts)}]


def clean_reply(text):
    text = re.sub(r"^\s*(sure|certainly|of course)[!,.]?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"[*_#`]+", "", text)  # small models sneak in markdown anyway
    return text.strip()


def define(term, mode, sentences, previous="", generate=None):
    """Returns dict: text, grounded (bool), snippets, ai (bool)."""
    context = find_context(term, sentences)
    if generate is None:
        from analysis.quiz_llm import llm_available, get_generator
        generate = get_generator() if llm_available() else None
    if generate is None:
        # no model installed: the best we can do is show where the lecture mentions it
        if context:
            return {"text": "From your lecture: " + " … ".join(context[:3]), "grounded": True,
                    "snippets": context, "ai": False}
        return {"text": "This term isn't in this lecture's material, and the AI model isn't installed.",
                "grounded": False, "snippets": [], "ai": False}
    _, max_tokens = MODES[mode]
    reply = clean_reply(generate(build_messages(term, mode, context, previous), max_tokens))
    return {"text": reply or "The model didn't return an answer. Try again.", "grounded": bool(context),
            "snippets": context, "ai": True}
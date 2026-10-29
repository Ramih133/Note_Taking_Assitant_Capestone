from difflib import SequenceMatcher

from sentence_transformers import SentenceTransformer, util


BULLETS = "•·▪◦‣–-* "

# Cleaning of the text, removing bullet poitns ect
def clean(text):
    return text.lstrip(BULLETS).strip()

def similar(a, b):
    return SequenceMatcher(None, clean(a).lower(), clean(b).lower()).ratio()

def fmt_time(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


# All Mini Model is used for comparing two sentences based on meaning
MODEL_NAME = "all-MiniLM-L6-v2"
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def encode(texts):
    return get_model().encode(texts, convert_to_tensor=True)


def cos_sim(a, b):
    return util.cos_sim(a, b)

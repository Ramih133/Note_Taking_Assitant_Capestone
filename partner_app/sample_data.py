import pymupdf

SLIDES = [
    ("Intro to Neural Networks", ["Week 6", "Prof. Smith"]),
    ("Outline", ["Perceptrons", "Activation Functions", "Backpropagation"]),
    ("Perceptrons", ["A perceptron is defined as a linear classifier", "y = w·x + b"]),
    ("Perceptron Limits", ["Cannot solve XOR", "Important: this will be on the exam"]),
    ("Activation Functions", ["ReLU: max(0, x)", "Sigmoid squashes to (0, 1)"]),
    ("Backpropagation", ["Uses the chain rule", "Never forget to zero the gradients"]),
]

NOTES = """
Perceptrons
- linear classifier
Activations
- ReLU
"""

TRANSCRIPT = [
    {"start": 312.0, "end": 320.0, "text": "So a single perceptron can't solve XOR, and that's going to be on the exam."},
    {"start": 320.0, "end": 328.0, "text": "That's exactly why we need hidden layers."},
    {"start": 905.0, "end": 914.0, "text": "Always zero your gradients before the backward pass or they accumulate."},
    {"start": 914.0, "end": 920.0, "text": "In PyTorch that's optimizer.zero_grad()."},
]


def make_test_deck(path="test_deck.pdf", with_outline=True):
    slides = list(SLIDES)
    if not with_outline:
        slides[1] = ("Welcome", ["Housekeeping", "Midterm next week"])
    doc = pymupdf.open()
    for title, bullets in slides:
        page = doc.new_page(width=960, height=540)
        page.insert_text((50, 70), title, fontsize=32)
        for i, b in enumerate(bullets):
            page.insert_text((70, 150 + i * 45), "• " + b, fontsize=20)
    doc.save(path)
    return path

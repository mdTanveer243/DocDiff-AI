# PDF Content Comparison Tool

A tool that compares two PDF documents (e.g. two versions of a contract or policy)
and produces a structured, color-coded report of what was added, removed, and
modified — including sentences that were **reworded/paraphrased** rather than
literally edited, which a plain text diff would miss.

## How it works (short version)

1. **Extract** text from both PDFs, page by page (`extractor.py`). Falls back to
   OCR if a page has almost no extractable text (i.e. it's a scanned image).
2. **Chunk** each page's text into sentences and clean up PDF artifacts like
   hyphenated line breaks (`chunker.py`).
3. **Align** the two sentence lists in two passes (`aligner.py`):
   - A structural pass using `difflib.SequenceMatcher` — cheaply finds
     unchanged / added / removed / "replace" regions and naturally handles
     reordering.
   - A semantic pass using `sentence-transformers` (`all-MiniLM-L6-v2`)
     embeddings + cosine similarity — run only inside the ambiguous "replace"
     regions, to match up reworded sentences that `difflib` alone would
     flag as unrelated add+delete.
4. **Classify** each modified pair as `trivial` (only whitespace/punctuation
   changed) or `substantive` (a number, date, or obligation word like
   "shall"/"must" changed) (`classifier.py`).
5. **Render** the result as a color-coded HTML report and a structured JSON
   export (`renderer.py`).

Color coding: 🟩 green = added, 🟥 red (strikethrough) = removed,
🟨 yellow = modified (tagged trivial/substantive with a confidence score).

## Project structure

```
pdf-compare/
├── README.md
├── requirements.txt
├── main.py
├── extractor.py
├── chunker.py
├── aligner.py
├── classifier.py
├── renderer.py
└── samples/
    ├── pair1_docA.pdf
    ├── pair1_docB.pdf
    ├── pair1_report.html
    ├── pair1_report.json
    ├── pair2_docA.pdf
    ├── pair2_docB.pdf
    ├── pair2_report.html
    └── pair2_report.json
```

## Setup

Requires Python 3.9+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The first run will download the `all-MiniLM-L6-v2` sentence-embedding model
(~80MB) from HuggingFace — needs an internet connection once.

**Optional (OCR support for scanned pages):** the OCR fallback uses
`pytesseract`, which needs the Tesseract binary installed on your system
separately from the Python package:

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki and
  add it to your PATH

If Tesseract isn't installed, everything still works for normal
(non-scanned) PDFs — the OCR fallback will just fail gracefully and log a
message for that page.

## Running it

```bash
python main.py docA.pdf docB.pdf --out report
```

This produces `report.html` (open in any browser) and `report.json`
(structured output).

To reproduce the sample outputs in `samples/`:

```bash
python main.py samples/pair1_docA.pdf samples/pair1_docB.pdf --out samples/pair1_report
python main.py samples/pair2_docA.pdf samples/pair2_docB.pdf --out samples/pair2_report
```

## Design decisions

- **`difflib` + embeddings, not embeddings alone**: matching every sentence
  in doc A against every sentence in doc B with embeddings is O(n²) and can
  misfire on repeated boilerplate. `difflib.SequenceMatcher` gives free,
  cheap structural alignment (and naturally handles sentences that just
  moved position), so embeddings only need to run on the small, genuinely
  ambiguous "replace" blocks.
- **Greedy matching over Hungarian/optimal assignment** inside a replace
  block: greedy top-score-first pairing is simpler and fast enough, since
  replace blocks are typically a handful of sentences, not hundreds. The
  loss in match optimality versus a true optimal assignment is negligible
  at this scale.
- **Similarity threshold (0.72)** for "this is a reword, not a new
  sentence" is a tunable constant in `aligner.py`. It was set by eyeballing
  scores on the sample pairs — moderately reworded legal sentences scored
  0.75–0.85, unrelated sentences scored well under 0.5.
- **Rule-based trivial/substantive classifier** instead of a trained model:
  regex-based number/date/obligation-word comparison is fully explainable
  (you can point at exactly why something was flagged) and needed no
  training data, which fit the timeline. A learned classifier is the
  natural next step (see Limitations).
- **Sentence-level granularity**, not paragraph-level: gives more precise
  localization of exactly which clause changed, at the cost of missing
  changes that involve one sentence being split into two (or merged).

## Known limitations

- OCR fallback is basic — it rasterizes the page and runs Tesseract with no
  layout reconstruction, so multi-column scanned pages may come out jumbled.
- Multi-column layouts in *text-based* (non-scanned) PDFs rely on PyMuPDF's
  default reading order, which can interleave columns incorrectly on
  complex layouts.
- Severity scoring is heuristic (regex-based), not learned — it won't catch
  substantive meaning changes that don't involve a number, date, or
  obligation keyword (e.g. a swapped party name, or "may" → "may not"
  phrased without those exact trigger words).
- Sentence splitting is regex-based, not a full NLP sentence tokenizer, so
  unusual punctuation (e.g. abbreviations like "Corp." or "Sec.") can
  occasionally cause an over-split.
- No merge/split detection: if one sentence in A becomes two sentences in
  B (or vice versa), the aligner will likely report this as a removal +
  addition rather than a single "modified" pair.

## What I'd do with more time

- Replace the rule-based trivial/substantive classifier with a small
  fine-tuned model trained on labeled contract-diff examples.
- Add a cross-encoder re-ranking step on top of the bi-encoder similarity
  for higher-precision paraphrase matching.
- Detect and handle multi-column layouts explicitly (e.g. via column
  bounding boxes from PyMuPDF's `page.get_text("blocks")`).
- Support sentence merge/split detection instead of only 1:1 alignment.
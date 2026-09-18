# DocDiff-AI — PDF Content Comparison Tool

Goes beyond a plain text diff — catches paraphrased clauses and changes
hidden inside tables using Sentence Transformer embeddings and structural
comparison, not just exact string matching.

A tool that compares two PDFs — contracts, policies, forms, quotes,
anything — and produces a structured, color-coded report of what was
added, removed, and modified. It catches two kinds of differences a plain
text diff would miss:

- **Reworded/paraphrased sentences** (e.g. "30 days" → "45 business days")
  via semantic similarity, not just exact string matching.
- **Changes buried inside tables** (e.g. an insurer name, a premium figure)
  via structural table extraction and row/cell-level diffing, not just
  flattened text.

The pipeline is generic — it makes no assumption about document type,
field names, or table structure. Verified against both a synthetic prose
contract and a real, table-heavy insurance quote pair.

## Tech stack

| Purpose | Library / Model |
|---|---|
| PDF text & table extraction | [`pdfplumber`](https://github.com/jsvine/pdfplumber) |
| OCR fallback (scanned pages) | [`PyMuPDF`](https://pymupdf.readthedocs.io/) (rasterization) + [`pytesseract`](https://github.com/madmaze/pytesseract) (Tesseract OCR) |
| Structural diffing | Python's built-in `difflib.SequenceMatcher` |
| Semantic similarity (paraphrase detection) | [`sentence-transformers`](https://www.sbert.net/) — **Sentence-BERT (SBERT)**, model: [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |
| Similarity computation | `numpy` (cosine similarity) |
| HTML report templating | `Jinja2` |
| Language | Python 3.9+ |

The core AI/ML component is **Sentence-BERT** (via the `sentence-transformers`
library), used to embed sentences and compare them by cosine similarity —
this is what lets the tool recognize that two differently-worded sentences
express the same underlying content, rather than reading them as an
unrelated deletion and addition.

## How it works

The pipeline runs two independent streams and reports both:

**1. Extract** (`src/extractor.py`)
Each page is split into two generic streams using `pdfplumber`:
- **Prose text** — everything on the page *outside* any detected table
  (found via bounding-box filtering, not by looking for specific text).
- **Tables** — structured row/column data for every table `pdfplumber`
  finds on the page.

If a page yields almost no extractable content in either stream, it's
treated as a scanned image and falls back to OCR (via PyMuPDF's pixmap
rendering + `pytesseract`).

**2. Chunk** (`src/chunker.py`)
The prose stream is split into comparable units using two generic patterns:
- `"Label: value"` on one line, or a label line followed by a lone `":"`
  line and the value on the next line (a layout artifact PDFs produce when
  a form field was rendered as a 3-column table).
- Everything else falls through to ordinary sentence splitting.

Label detection is shape-based (short line, ALL CAPS or mostly Title Case,
no terminal punctuation) — not a list of known field names — so it works
whether the document is a legal contract or a form.

**3. Align text** (`src/aligner.py`) — two passes:
- A structural pass using `difflib.SequenceMatcher`, which cheaply finds
  unchanged/added/removed/"replace" regions and naturally handles sentences
  that just moved position.
- A semantic pass using **Sentence-BERT embeddings** (`all-MiniLM-L6-v2`,
  via `sentence-transformers`) + cosine similarity, run only inside the
  ambiguous "replace" regions, to match up reworded sentences that
  `difflib` alone would flag as unrelated add+delete.

**4. Diff tables** (`src/table_differ.py`)
Tables extracted from each document are matched to each other by
header/first-row similarity (using global best-score-first assignment, not
document order — position-based matching would incorrectly pair, say, an
unrelated clause table with a data table just because it came first). Matched
tables are then diffed row-by-row (`difflib`) and, within a modified row,
cell-by-cell.

**5. Classify** (`src/classifier.py`)
Every modified pair (text or table) is tagged `trivial` (only
whitespace/punctuation changed) or `substantive`. Substantive triggers:
a changed number or date, a changed obligation word (`shall`/`must`/etc.),
or — as a generic fallback — low word overlap between the two versions,
which catches things like an entity/name swap that doesn't involve any
number or keyword at all.

**6. Render** (`src/renderer.py` + `templates/report.html.j2`)
Produces a single color-coded HTML report (Text Differences + Table
Differences sections — the table section only appears if the documents
actually contain tables) and a structured JSON export.

Color coding: 🟩 green = added, 🟥 red (strikethrough) = removed,
🟨 yellow = modified (tagged trivial/substantive with a similarity score).

## Project structure

```
pdf-compare/
├── README.md
├── APPROACH.md
├── requirements.txt
├── main.py
├── make_samples.py
├── test_aligner.py
├── src/
│   ├── __init__.py
│   ├── extractor.py
│   ├── chunker.py
│   ├── aligner.py
│   ├── classifier.py
│   ├── table_differ.py
│   └── renderer.py
├── templates/
│   └── report.html.j2
├── samples/
│   ├── pair1_docA.pdf          # synthetic prose contract pair
│   ├── pair1_docB.pdf
│   ├── Quotes_QS1936.pdf       # real table-heavy insurance quote pair
│   └── Quotes_QS1937.pdf
└── Reports/                     # generated output — created automatically
    ├── pair1_report.html
    ├── pair1_report.json
    ├── quotes_report.html
    └── quotes_report.json
```

## Setup

Requires Python 3.9+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The first run downloads the Sentence-BERT model `all-MiniLM-L6-v2`
(~80MB) from Hugging Face — needs an internet connection once, then it's
cached locally.

**Optional (OCR support for scanned pages):** the OCR fallback uses
`pytesseract`, which needs the Tesseract binary installed separately from
the Python package:

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki and
  add it to your PATH

If Tesseract isn't installed, everything still works for normal
(non-scanned) PDFs — the OCR fallback fails gracefully and logs a message
for that page.

## Running it

```bash
python main.py docA.pdf docB.pdf --out Reports/my_report
```

This produces `Reports/my_report.html` (open in any browser) and
`Reports/my_report.json` (structured output). The `Reports/` folder is
created automatically if it doesn't exist. If you omit `--out` entirely,
it defaults to `Reports/report`.

To generate the synthetic sample pair and reproduce both sample outputs:

```bash
python make_samples.py

python main.py samples/pair1_docA.pdf samples/pair1_docB.pdf --out Reports/pair1_report
python main.py samples/Quotes_QS1936.pdf samples/Quotes_QS1937.pdf --out Reports/quotes_report
```

To sanity-check the core comparison logic:

```bash
python test_aligner.py
```

## Design decisions

- **Two independent streams (prose vs. tables)** instead of one flattened
  text stream: plain-text extraction collapses a table's rows and columns
  into one run-on line, which destroys exactly the structure needed to
  catch a change buried in one cell (e.g. an insurer name). Splitting
  tables out via `pdfplumber` bounding boxes and diffing them structurally
  is what makes that catch possible.
- **`difflib` + Sentence-BERT, not embeddings alone**, for prose: matching
  every sentence in doc A against every sentence in doc B with embeddings
  is O(n²) and can misfire on repeated boilerplate. `difflib.SequenceMatcher`
  gives free, cheap structural alignment, so embeddings only need to run on
  the small, genuinely ambiguous "replace" blocks.
- **Global best-score-first table matching**, not document order: an early
  greedy version paired tables by iterating in order, which let a weak
  match (score 0.32) grab a table before a much stronger match (score 1.0)
  for the same table got a chance. Sorting all candidate pairs by score
  first and assigning greedily from the top fixes this — the same
  principle used for sentence matching inside a replace block.
- **Shape-based label detection**, not a field-name list: a line is
  treated as a label if it's short, has no terminal punctuation, and is
  ALL CAPS or mostly Title Case — not because it matches a known field
  name. This is what lets the same chunker handle a legal contract (falls
  through entirely to sentence splitting) and a form (mostly label/value
  detection) with no configuration switch.
- **Word-overlap fallback in the classifier**: number/date/obligation-word
  rules alone missed a real case — an entity name changing (e.g. one
  insurer swapped for another) with no numbers or trigger words involved.
  Adding "flag as substantive if word overlap between the two versions is
  low" catches this generically, without hardcoding domain vocabulary.
- **Greedy matching over Hungarian/optimal assignment** inside a text
  replace block: simpler and fast enough, since replace blocks are
  typically a handful of sentences, not hundreds.
- **Similarity threshold (0.72)** for "this is a reword, not a new
  sentence" is a tunable constant in `aligner.py`, set by eyeballing scores
  on sample pairs — moderately reworded legal sentences scored 0.75–0.85,
  unrelated sentences scored well under 0.5.
- **Sentence-level granularity**, not paragraph-level: more precise
  localization of exactly which clause changed, at the cost of missing
  changes that involve one sentence splitting into two (or merging).

## Known limitations

- OCR fallback is basic — it rasterizes the page and runs Tesseract with no
  layout reconstruction, so multi-column scanned pages may come out jumbled.
- Table row matching inside a "replace" block is position-based (not
  embedding-based like the prose aligner), so a table where rows were
  reordered *and* reworded at the same time may mismatch.
- Sentence splitting is regex-based, not a full NLP tokenizer, so unusual
  punctuation (e.g. abbreviations like "Corp." or "Sec.") can occasionally
  cause an over-split.
- No merge/split detection: if one sentence (or table row) in A becomes two
  in B, the aligner will likely report a removal + addition rather than a
  single "modified" pair.
- The word-overlap substantive fallback is a blunt instrument — it can't
  distinguish "most of the wording changed but the meaning didn't" from
  "most of the wording changed and the meaning did."

## What I'd do with more time

- Replace the rule-based trivial/substantive classifier with a small
  fine-tuned model trained on labeled contract-diff examples.
- Add a cross-encoder re-ranking step on top of the SBERT bi-encoder
  similarity for higher-precision paraphrase matching.
- Apply embedding-based row matching to tables (currently position-based
  within a replace block), matching the approach already used for prose.
- Support sentence/row merge-split detection instead of only 1:1 alignment.

See `APPROACH.md` for a shorter, interview-facing summary of the design.

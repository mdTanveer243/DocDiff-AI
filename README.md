# Approach

## What this is

A tool that compares two PDFs and reports what was added, removed, or
modified — including changes a plain text diff would miss: reworded
sentences ("30 days" → "45 business days") and changes buried inside
tables (e.g. an insurer name swapped in a policy schedule). It's built to
work on any PDF pair, not tuned to one document type — verified against
both a synthetic prose contract and a real, table-heavy insurance quote
pair.

## Extraction

Each page is split into two streams using `pdfplumber`: **prose text**
(everything outside a detected table, found via bounding-box filtering)
and **tables** (structured rows/columns via `pdfplumber.find_tables()`).
This split matters more than it sounds — a naive plain-text extraction
flattens a table's rows and columns into one run-on line, which destroys
exactly the structure needed to catch a change buried in a single cell.
Pages with almost no extractable content in either stream are treated as
scanned images and OCR'd via Tesseract.

## Comparison logic

**Prose** is aligned in two passes: `difflib.SequenceMatcher` does a cheap
structural pass first (free handling of reordering, minimal work for
unchanged content), then sentence-embedding cosine similarity
(`all-MiniLM-L6-v2`) runs only inside the ambiguous "replace" regions to
catch reworded sentences that `difflib` alone would call unrelated
add+delete.

**Tables** are matched to each other across the two documents by
header/first-row similarity, using global best-score-first assignment
(not document order — an early version assigned in order and let a weak
match grab a table before a much stronger match for the same table got a
chance; sorting all candidate pairs first fixes this). Matched tables are
then diffed row-by-row and, within a modified row, cell-by-cell.

Every modified pair, text or table, is tagged `trivial` or `substantive`:
a changed number/date/obligation-word (`shall`/`must`) triggers
substantive, and as a fallback, so does low word-overlap between the two
versions — which is what catches something like an entity name changing
with no numbers or keywords involved at all.

## The AI/ML component

Sentence-transformer embeddings + cosine similarity are what let the tool
go beyond exact string matching: two sentences with almost no shared words
but the same meaning still get correctly paired as "modified" rather than
scored as an unrelated add/delete. This only runs where `difflib` can't
already resolve the alignment cheaply, keeping the embedding cost small
even on longer documents.

## Output

A single HTML report (color-coded: green/red/yellow) with two sections —
Text Differences and Table Differences, the latter only appearing when the
documents actually contain tables — plus a structured JSON export of the
same data.

## What I'd do with more time

- Apply the same embedding-based matching used for prose to table rows
  (currently position-based within a replace block, so a table that's
  both reordered and reworded at once could mismatch).
- Replace the rule-based trivial/substantive classifier with a small
  model trained on labeled diff examples — the current word-overlap
  fallback is a blunt instrument that can't distinguish "most wording
  changed, meaning didn't" from "meaning changed too."
- Handle sentence/row merge-split (one unit becoming two, or vice versa),
  which the current 1:1 alignment doesn't support.



## Setup

Requires Python 3.9+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The first run downloads the `all-MiniLM-L6-v2` sentence-embedding model
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
  text stream: PyMuPDF-style plain-text extraction collapses a table's
  rows and columns into one run-on line, which destroys exactly the
  structure needed to catch a change buried in one cell (e.g. an insurer
  name). Splitting tables out via `pdfplumber` bounding boxes and diffing
  them structurally is what makes that catch possible.
- **`difflib` + embeddings, not embeddings alone**, for prose: matching
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
  reordered *and* reworded at the same time may mismatch — a natural next
  step would be to apply the same embedding-based matching used for prose
  to table rows.
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
- Add a cross-encoder re-ranking step on top of the bi-encoder similarity
  for higher-precision paraphrase matching.
- Apply embedding-based row matching to tables (currently position-based
  within a replace block), matching the approach already used for prose.
- Support sentence/row merge-split detection instead of only 1:1 alignment.

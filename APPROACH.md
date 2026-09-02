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
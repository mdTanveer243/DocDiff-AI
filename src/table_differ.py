"""
Universal table comparison.

Takes the raw table lists produced by extractor.py (one list of tables per
page, each table a list-of-rows-of-cells — pdfplumber's native format) and
diffs them structurally: which rows are unchanged/added/removed/modified,
and within a modified row, which cells actually changed.

Nothing here is specific to any document type or column name. Tables from
the two documents are matched to each other by content similarity (their
header row, or their first row if no clear header), not by position —
so this still works if a table was added, removed, or reordered between
the two documents.
"""
import difflib


def _flatten_table_signature(table):
    """A short signature used only to match tables across documents (not for diffing)."""
    header = table[0] if table else []
    return " ".join(str(c) for c in header if c)


def _row_text(row):
    return " | ".join(str(c) if c is not None else "" for c in row)


def match_tables(tables_a, tables_b, threshold=0.5):
    """
    Pairs up tables from doc A and doc B by header/first-row similarity.
    Uses global best-score-first assignment (like the sentence aligner) so
    a weak match doesn't block a later, much stronger match for the same
    table — e.g. if table A[0] weakly resembles B[0] (score 0.32) but
    A[2] is a near-perfect match for B[0] (score 1.0), A[2] must win B[0].
    """
    candidates = sorted(
        (
            (difflib.SequenceMatcher(None, _flatten_table_signature(ta), _flatten_table_signature(tb)).ratio(), i, j)
            for i, ta in enumerate(tables_a) for j, tb in enumerate(tables_b)
        ),
        reverse=True,
    )
    used_a, used_b, pairs = set(), set(), []
    for score, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        if score >= threshold:
            used_a.add(i)
            used_b.add(j)
            pairs.append((i, j))

    for i in range(len(tables_a)):
        if i not in used_a:
            pairs.append((i, None))  # table only in A
    for j in range(len(tables_b)):
        if j not in used_b:
            pairs.append((None, j))  # table only in B
    return pairs


def diff_cells(row_a, row_b):
    """Returns list of (cell_a, cell_b, changed) for cells aligned by position."""
    n = max(len(row_a), len(row_b))
    out = []
    for k in range(n):
        ca = row_a[k] if k < len(row_a) else None
        cb = row_b[k] if k < len(row_b) else None
        changed = (str(ca or "").strip() != str(cb or "").strip())
        out.append((ca, cb, changed))
    return out


def diff_table_pair(table_a, table_b):
    """Row-level diff of two matched tables using difflib on row text."""
    rows_a = [_row_text(r) for r in table_a]
    rows_b = [_row_text(r) for r in table_b]
    matcher = difflib.SequenceMatcher(None, rows_a, rows_b, autojunk=False)

    results = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                results.append({"type": "unchanged", "row_a": table_a[i1 + k], "row_b": table_b[j1 + k]})
        elif tag == "delete":
            for r in table_a[i1:i2]:
                results.append({"type": "removed", "row_a": r, "row_b": None})
        elif tag == "insert":
            for r in table_b[j1:j2]:
                results.append({"type": "added", "row_a": None, "row_b": r})
        elif tag == "replace":
            # Pair rows within the replace block position-wise (tables are
            # usually short enough that this is a reasonable default; a
            # more advanced version could embed rows like the prose aligner does).
            a_block, b_block = table_a[i1:i2], table_b[j1:j2]
            for k in range(max(len(a_block), len(b_block))):
                ra = a_block[k] if k < len(a_block) else None
                rb = b_block[k] if k < len(b_block) else None
                if ra is None:
                    results.append({"type": "added", "row_a": None, "row_b": rb})
                elif rb is None:
                    results.append({"type": "removed", "row_a": ra, "row_b": None})
                else:
                    results.append({"type": "modified", "row_a": ra, "row_b": rb, "cells": diff_cells(ra, rb)})
    return results


def diff_all_tables(tables_a, tables_b):
    """
    tables_a / tables_b: list of tables per page, e.g. page["tables"] from
    extractor.py, flattened across all pages of each document.
    Returns a list of {table_index_a, table_index_b, rows: [...]}.
    """
    pairs = match_tables(tables_a, tables_b)
    output = []
    for ia, ib in pairs:
        if ia is not None and ib is not None:
            rows = diff_table_pair(tables_a[ia], tables_b[ib])
        elif ia is not None:
            rows = [{"type": "removed", "row_a": r, "row_b": None} for r in tables_a[ia]]
        else:
            rows = [{"type": "added", "row_a": None, "row_b": r} for r in tables_b[ib]]
        output.append({"table_index_a": ia, "table_index_b": ib, "rows": rows})
    return output
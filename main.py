import argparse
import json
import os
from src.extractor import extract_pages
from src.chunker import chunk_pages
from src.aligner import align_documents
from src.classifier import classify_change
from src.table_differ import diff_all_tables
from src.renderer import build_report


def _row_text(row):
    if row is None:
        return ""
    return " | ".join(str(c) if c is not None else "" for c in row)


def compare_pdfs(pdf_a_path, pdf_b_path, out_prefix="Reports/report"):
    pages_a = extract_pages(pdf_a_path)
    pages_b = extract_pages(pdf_b_path)

    # --- prose stream (sentence + label/field aware) ---
    units_a = chunk_pages(pages_a)
    units_b = chunk_pages(pages_b)
    text_results = align_documents(units_a, units_b)
    for r in text_results:
        if r["type"] == "modified":
            r["severity"] = classify_change(r["a"].text, r["b"].text)

    # --- table stream (generic, any column layout) ---
    tables_a = [t for p in pages_a for t in p["tables"]]
    tables_b = [t for p in pages_b for t in p["tables"]]
    table_results = diff_all_tables(tables_a, tables_b)
    for t in table_results:
        for row in t["rows"]:
            if row["type"] == "modified":
                a_text = _row_text(row["row_a"])
                b_text = _row_text(row["row_b"])
                row["severity"] = classify_change(a_text, b_text)

    html, data = build_report(text_results, table_results)

    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)

    with open(f"{out_prefix}.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(f"{out_prefix}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Done. Text: {data['text_summary']} | Tables: {data['table_summary']}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two PDF documents.")
    parser.add_argument("pdf_a")
    parser.add_argument("pdf_b")
    parser.add_argument("--out", default="Reports/report")
    args = parser.parse_args()
    compare_pdfs(args.pdf_a, args.pdf_b, args.out)
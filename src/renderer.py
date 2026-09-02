import os
from jinja2 import Environment, FileSystemLoader

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # one level up from src/
_TEMPLATE_DIR = os.path.join(_REPO_ROOT, "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
_template = _env.get_template("report.html.j2")


def _row_cells(row):
    if row is None:
        return []
    return [str(c) if c is not None else "" for c in row]


def build_report(text_results, table_results):
    # --- text/prose summary ---
    text_items = []
    text_summary = {"total": 0, "unchanged": 0, "added": 0, "removed": 0, "modified": 0, "trivial": 0, "substantive": 0}
    for r in text_results:
        text_summary["total"] += 1
        text_summary[r["type"]] += 1
        item = {
            "type": r["type"],
            "a_text": r["a"].text if r["a"] else None,
            "b_text": r["b"].text if r["b"] else None,
            "a_page": r["a"].page_num if r["a"] else None,
            "b_page": r["b"].page_num if r["b"] else None,
        }
        if r["type"] == "modified":
            item["severity"] = r["severity"]
            item["score"] = round(r["score"], 2)
            text_summary[r["severity"]] += 1
        text_items.append(item)

    # --- table summary ---
    table_summary = {"tables_compared": len(table_results), "unchanged": 0, "added": 0, "removed": 0, "modified": 0, "trivial": 0, "substantive": 0}
    table_blocks = []
    for t in table_results:
        rows_out = []
        for row in t["rows"]:
            table_summary[row["type"]] += 1
            entry = {
                "type": row["type"],
                "row_a": _row_cells(row.get("row_a")),
                "row_b": _row_cells(row.get("row_b")),
            }
            if row["type"] == "modified":
                entry["severity"] = row["severity"]
                table_summary[row["severity"]] += 1
                entry["cells"] = row.get("cells", [])
            rows_out.append(entry)
        table_blocks.append({
            "table_index_a": t["table_index_a"],
            "table_index_b": t["table_index_b"],
            "rows": rows_out,
        })

    html = _template.render(
        text_summary=text_summary,
        text_items=text_items,
        table_summary=table_summary,
        table_blocks=table_blocks,
    )
    data = {
        "text_summary": text_summary,
        "text_differences": text_items,
        "table_summary": table_summary,
        "table_differences": table_blocks,
    }
    return html, data
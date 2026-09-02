"""
Universal PDF extractor.

For every page, splits content into two generic streams:
  - "prose": all text on the page that does NOT fall inside a detected table
  - "tables": structured row/column data for every table pdfplumber finds

This split works for any PDF — a plain prose contract has zero tables and
everything lands in "prose"; a table-heavy form has most content in
"tables" and only headers/labels land in "prose". Nothing here assumes a
particular document type or field name.

Falls back to OCR (via PyMuPDF's pixmap + pytesseract) when a page yields
almost no extractable text/tables at all — the signal for "this page is a
scanned image", not a schema of any specific document.
"""
import pdfplumber
import fitz  # PyMuPDF, used only for the OCR fallback rasterization


def extract_pages(pdf_path, ocr_fallback=True, min_chars_before_ocr=20):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.find_tables()
            table_data = [t.extract() for t in tables]

            if tables:
                bboxes = [t.bbox for t in tables]

                def outside_all_tables(obj, bboxes=bboxes):
                    for (x0, top, x1, bottom) in bboxes:
                        if x0 <= obj.get("x0", -1) <= x1 and top <= obj.get("top", -1) <= bottom:
                            return False
                    return True

                prose_text = page.filter(outside_all_tables).extract_text() or ""
            else:
                prose_text = page.extract_text() or ""

            total_content_len = len(prose_text.strip()) + sum(
                len(str(cell)) for row in table_data for cell in row if cell
            )
            ocr_used = False
            if ocr_fallback and total_content_len < min_chars_before_ocr:
                prose_text = _ocr_page(pdf_path, i)
                table_data = []
                ocr_used = True

            pages.append({
                "page_num": i + 1,
                "prose_text": prose_text,
                "tables": table_data,
                "ocr_used": ocr_used,
            })
    return pages


def _ocr_page(pdf_path, page_index, dpi=200):
    try:
        import pytesseract
        from PIL import Image
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return pytesseract.image_to_string(img).strip()
    except Exception as e:
        print(f"OCR failed on page {page_index + 1}: {e}")
        return ""
"""
Universal chunker for the non-table "prose" stream produced by extractor.py.

Detects two generic line shapes, neither tied to any specific field name:
  (a) "Label: value" on a single line  (e.g. "Governing Law: Delaware",
      "CLASS OF INSURANCE: ALL RISKS")
  (b) A short label line, followed by a line that is exactly ":",
      followed by the value on the next line(s) — an artifact of PDFs
      whose form fields were laid out as a 3-column table (label | ':' |
      value) and extracted as three separate text lines.
Anything that doesn't match either shape is treated as ordinary prose and
sentence-split. This means the same chunker handles a plain-text contract
(no labels at all — falls through entirely to sentence splitting) and a
label-heavy form (mostly pattern a/b) without configuration.
"""
import re

# Label lines are short (not a full sentence) and don't already end with
# sentence punctuation — this is what distinguishes "Client:" from
# "He said the deal was final: everyone agreed." (that colon sits inside
# a long sentence, so it won't match the length/shape constraints below).
_FIELD_INLINE_RE = re.compile(r'^([^\n:]{2,45}?)\s*:\s*(\S.*)$')
_LABEL_ONLY_RE = re.compile(r'^[^\n:]{2,45}$')
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\(])')


class Unit:
    def __init__(self, text, page_num, field=None):
        self.text = text.strip()
        self.page_num = page_num
        self.field = field
        self.norm = re.sub(r'\s+', ' ', self.text.lower()).strip()

    def __repr__(self):
        tag = f"[{self.field}] " if self.field else ""
        return f"<Unit p{self.page_num} {tag}{self.text[:50]}>"


def _looks_like_label(line):
    """
    A label line is short, has no terminal sentence punctuation, and is
    either ALL CAPS or mostly Title Case — the two conventions actually
    used for form/field labels. This deliberately rejects ordinary
    sentence fragments that happen to contain a colon (e.g. "He said the
    deal was final") because in normal prose only the first word is
    capitalized, not most of them.
    """
    if not _LABEL_ONLY_RE.match(line):
        return False
    if line.endswith((".", "!", "?", ",")):
        return False
    words = line.split()
    if not words or len(words) > 6:
        return False
    if line.isupper():
        return True
    capitalized = sum(1 for w in words if w[:1].isupper())
    return capitalized / len(words) >= 0.6


def _split_prose(text):
    return [p.strip() for p in _SENT_SPLIT.split(text.strip()) if len(p.strip()) > 2]


def clean_page_text(text):
    text = re.sub(r'-\n', '', text)
    return text


def chunk_pages(pages, prose_threshold=100):
    units = []
    for page in pages:
        raw = page.get("prose_text", page.get("text", ""))
        raw = clean_page_text(raw)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]

        current_field = None
        buffer = []
        i = 0

        def flush(field):
            if not buffer:
                return
            joined = " ".join(buffer).strip()
            if len(joined) > prose_threshold:
                for s in _split_prose(joined):
                    units.append(Unit(s, page["page_num"], field=field))
            else:
                units.append(Unit(joined, page["page_num"], field=field))
            buffer.clear()

        while i < len(lines):
            line = lines[i]

            # Pattern (b): label line, next line is exactly ":"
            if _looks_like_label(line) and i + 1 < len(lines) and lines[i + 1] == ":":
                flush(current_field)
                current_field = line
                buffer.append(f"{line}:")
                i += 2
                continue

            # Pattern (a): "Label: value" inline — only treat as a field if
            # the part before the colon is short (a label), not a sentence
            # fragment that merely happens to contain a colon.
            m = _FIELD_INLINE_RE.match(line)
            if m and _looks_like_label(m.group(1)):
                flush(current_field)
                label, value = m.group(1).strip(), m.group(2).strip()
                current_field = label
                buffer.append(f"{label}: {value}")
                i += 1
                continue

            buffer.append(line)
            i += 1

        flush(current_field)
    return units
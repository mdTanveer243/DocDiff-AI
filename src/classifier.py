import re

_NUM_RE = re.compile(r'\d+(?:\.\d+)?')
_DATE_RE = re.compile(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b')
_OBLIGATION_WORDS = {"shall", "must", "will", "required", "obligated", "entitled", "may not", "prohibited"}

# Below this word-overlap ratio, treat the change as substantive even when
# no number/date/obligation-word trigger fired — this is what catches a
# pure entity-name swap (e.g. an insurer or counterparty changing) or a
# heavily reworded clause, without hardcoding any domain vocabulary.
_WORD_OVERLAP_SUBSTANTIVE_THRESHOLD = 0.5


def _normalize_for_trivial(text):
    t = text.lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _word_set(text):
    return {w.lower().strip('.,;:()[]') for w in text.split() if w.strip('.,;:()[]')}


def classify_change(text_a, text_b):
    if _normalize_for_trivial(text_a) == _normalize_for_trivial(text_b):
        return "trivial"

    nums_a = set(_NUM_RE.findall(text_a)) | set(_DATE_RE.findall(text_a))
    nums_b = set(_NUM_RE.findall(text_b)) | set(_DATE_RE.findall(text_b))
    if nums_a != nums_b:
        return "substantive"

    words_a = _word_set(text_a)
    words_b = _word_set(text_b)
    if (words_a & _OBLIGATION_WORDS) != (words_b & _OBLIGATION_WORDS):
        return "substantive"

    # Generic fallback: how much of the wording actually stayed the same?
    # Low overlap means most of the content changed (e.g. a name swap, a
    # reworded clause) even though it didn't trip a number/date/obligation
    # rule specifically.
    if words_a or words_b:
        overlap = len(words_a & words_b) / len(words_a | words_b)
        if overlap < _WORD_OVERLAP_SUBSTANTIVE_THRESHOLD:
            return "substantive"

    return "trivial"
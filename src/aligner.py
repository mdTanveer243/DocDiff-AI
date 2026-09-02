import difflib
import numpy as np
from sentence_transformers import SentenceTransformer

_model = None
def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def cosine_sim_matrix(a_embs, b_embs):
    a_norm = a_embs / np.linalg.norm(a_embs, axis=1, keepdims=True)
    b_norm = b_embs / np.linalg.norm(b_embs, axis=1, keepdims=True)
    return a_norm @ b_norm.T


def match_block(a_block, b_block, model, threshold=0.72):
    if not a_block:
        return [{"type": "added", "a": None, "b": b} for b in b_block]
    if not b_block:
        return [{"type": "removed", "a": a, "b": None} for a in a_block]

    a_embs = model.encode([s.text for s in a_block])
    b_embs = model.encode([s.text for s in b_block])
    sim = cosine_sim_matrix(a_embs, b_embs)

    candidates = sorted(
        ((sim[i][j], i, j) for i in range(len(a_block)) for j in range(len(b_block))),
        reverse=True
    )
    used_a, used_b, results = set(), set(), []
    for score, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        if score >= threshold:
            used_a.add(i)
            used_b.add(j)
            results.append({"type": "modified", "a": a_block[i], "b": b_block[j], "score": float(score)})

    for i, a in enumerate(a_block):
        if i not in used_a:
            results.append({"type": "removed", "a": a, "b": None})
    for j, b in enumerate(b_block):
        if j not in used_b:
            results.append({"type": "added", "a": None, "b": b})
    return results


def align_documents(sents_a, sents_b, threshold=0.72):
    model = get_model()
    matcher = difflib.SequenceMatcher(
        None,
        [s.norm for s in sents_a],
        [s.norm for s in sents_b],
        autojunk=False
    )

    results = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                results.append({"type": "unchanged", "a": sents_a[i1 + k], "b": sents_b[j1 + k]})
        elif tag == "delete":
            for a in sents_a[i1:i2]:
                results.append({"type": "removed", "a": a, "b": None})
        elif tag == "insert":
            for b in sents_b[j1:j2]:
                results.append({"type": "added", "a": None, "b": b})
        elif tag == "replace":
            results.extend(match_block(sents_a[i1:i2], sents_b[j1:j2], model, threshold))

    return results
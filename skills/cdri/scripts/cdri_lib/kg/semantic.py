"""Semantic node search. Default: TF-IDF cosine over node text (stdlib, deterministic, offline). If
CDRI_EMBEDDINGS=1 and sentence-transformers is installed, a local embedding model is used instead (the model
runs locally; no text is sent to an external service)."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from typing import Dict, List, Optional

from .store import KnowledgeBase

_TOK = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")
STOP = set("the a an of and or in on for to with by from is are be as at this that we our using via".split())


def _tokens(text: str) -> List[str]:
    return [t for t in _TOK.findall(text.lower()) if t not in STOP and len(t) > 1 or "\u4e00" <= t <= "\u9fff"]


def node_text(n: dict) -> str:
    p = n.get("props") or {}
    parts = [n["label"], n["type"]]
    for k in ("abstract", "definition", "aliases", "signature", "formulation", "mechanism", "rationale", "question"):
        v = p.get(k)
        if v:
            parts.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    return " ".join(parts)


def tfidf_search(kb: KnowledgeBase, query: str, types: Optional[List[str]] = None, k: int = 20) -> List[dict]:
    nodes = [n for n in kb.nodes() if not types or n["type"] in types]
    docs = [Counter(_tokens(node_text(n))) for n in nodes]
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    N = len(docs) or 1
    idf = {t: math.log((N + 1) / (c + 1)) + 1 for t, c in df.items()}

    def vec(c: Counter) -> Dict[str, float]:
        return {t: (1 + math.log(v)) * idf.get(t, math.log(N + 1) + 1) for t, v in c.items()}

    q = vec(Counter(_tokens(query)))
    qn = math.sqrt(sum(v * v for v in q.values())) or 1
    out = []
    for n, d in zip(nodes, docs):
        v = vec(d)
        dot = sum(q[t] * v.get(t, 0) for t in q)
        if dot <= 0:
            continue
        s = dot / (qn * (math.sqrt(sum(x * x for x in v.values())) or 1))
        out.append({"id": n["id"], "type": n["type"], "label": n["label"], "score": round(s, 4),
                    "status": n["status"], "scope": n.get("scope"), "method": "tfidf"})
    return sorted(out, key=lambda x: -x["score"])[:k]


def embedding_search(kb: KnowledgeBase, query: str, types: Optional[List[str]] = None, k: int = 20) -> List[dict]:
    from sentence_transformers import SentenceTransformer  # optional dependency
    model = SentenceTransformer(os.environ.get("CDRI_EMBED_MODEL", "all-MiniLM-L6-v2"))
    nodes = [n for n in kb.nodes() if not types or n["type"] in types]
    if not nodes:
        return []
    embs = model.encode([node_text(n) for n in nodes] + [query], normalize_embeddings=True)
    qv = embs[-1]
    scored = [(float((embs[i] * qv).sum()), n) for i, n in enumerate(nodes)]
    scored.sort(key=lambda x: -x[0])
    return [{"id": n["id"], "type": n["type"], "label": n["label"], "score": round(s, 4), "status": n["status"],
             "scope": n.get("scope"), "method": "embedding"} for s, n in scored[:k]]


def search(kb: KnowledgeBase, query: str, types: Optional[List[str]] = None, k: int = 20) -> Dict[str, object]:
    if os.environ.get("CDRI_EMBEDDINGS") == "1":
        try:
            return {"method": "embedding", "hits": embedding_search(kb, query, types, k)}
        except ImportError:
            return {"method": "tfidf", "hits": tfidf_search(kb, query, types, k),
                    "note": "CDRI_EMBEDDINGS=1 but sentence-transformers is not installed; used TF-IDF"}
    return {"method": "tfidf", "hits": tfidf_search(kb, query, types, k)}

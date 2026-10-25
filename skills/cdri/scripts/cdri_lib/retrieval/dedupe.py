"""Deduplication and version linking (preprint <-> published) across sources."""

from __future__ import annotations

from typing import Dict, List

from ..ids import norm_text, title_similarity
from .records import Record, is_preprint_doi

STATUS_RANK = {"published": 3, "accepted": 2, "preprint": 1, "unknown": 0}


class _UF:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _is_preprint(r: Record) -> bool:
    return r.pub_status == "preprint" or (bool(r.arxiv) and not r.doi) or is_preprint_doi(r.doi)


def deduplicate(records: List[Record], title_threshold: float = 0.93) -> List[Record]:
    n = len(records)
    uf = _UF(n)
    keys: Dict[str, int] = {}
    for i, r in enumerate(records):
        for k in (f"doi:{r.doi}" if r.doi else None, f"arxiv:{r.arxiv}" if r.arxiv else None,
                  f"pmid:{r.pmid}" if r.pmid else None, f"pmcid:{r.pmcid}" if r.pmcid else None,
                  f"oa:{r.openalex}" if r.openalex else None, f"s2:{r.s2}" if r.s2 else None):
            if k is None:
                continue
            if k in keys:
                uf.union(keys[k], i)
            else:
                keys[k] = i
    # title-based merge (blocked by first two normalized tokens)
    blocks: Dict[str, List[int]] = {}
    for i, r in enumerate(records):
        toks = norm_text(r.title).split()
        if len(toks) >= 3:
            blocks.setdefault(" ".join(toks[:2]), []).append(i)
    for idx in blocks.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                if uf.find(i) == uf.find(j):
                    continue
                ri, rj = records[i], records[j]
                ydiff = abs((ri.year or 0) - (rj.year or 0)) if ri.year and rj.year else 0
                max_diff = 2 if (_is_preprint(ri) or _is_preprint(rj)) else 1
                if ydiff <= max_diff and title_similarity(ri.title, rj.title) >= title_threshold:
                    uf.union(i, j)
    groups: Dict[int, List[Record]] = {}
    for i, r in enumerate(records):
        groups.setdefault(uf.find(i), []).append(r)
    return [merge(g) for g in groups.values()]


def merge(group: List[Record]) -> Record:
    if len(group) == 1:
        return group[0]
    pubs = [r for r in group if not _is_preprint(r)]
    pres = [r for r in group if _is_preprint(r)]
    base_pool = pubs or group
    base = max(base_pool, key=lambda r: (STATUS_RANK.get(r.pub_status, 0), bool(r.abstract), r.citations or 0))
    m = Record.from_dict(base.to_dict())
    for r in group:
        for f in ("doi", "arxiv", "pmid", "pmcid", "openalex", "s2", "abstract", "oa_url", "date", "url"):
            if not getattr(m, f) and getattr(r, f):
                setattr(m, f, getattr(r, f))
        if r.citations is not None:
            m.citations = max(m.citations or 0, r.citations)
        if len(r.authors) > len(m.authors):
            m.authors = r.authors
        m.references = m.references or r.references
        for fb in r.found_by:
            if fb not in m.found_by:
                m.found_by.append(fb)
        for s in r.sources:
            if s not in m.sources:
                m.sources.append(s)
        for v in r.versions:
            if v not in m.versions:
                m.versions.append(v)
    if pubs and pres:
        for p in pres:
            v = {"relation": "preprint_version", "arxiv": p.arxiv, "doi": p.doi if is_preprint_doi(p.doi) else None,
                 "venue": p.venue, "date": p.date, "source_db": p.source_db}
            if v not in m.versions:
                m.versions.append(v)
        if m.doi and is_preprint_doi(m.doi):
            pub_doi = next((p.doi for p in pubs if p.doi and not is_preprint_doi(p.doi)), None)
            if pub_doi:
                m.doi = pub_doi
    statuses = {r.source_db: (r.pub_status, r.status_evidence) for r in group}
    best = max(group, key=lambda r: STATUS_RANK.get(r.pub_status, 0))
    m.pub_status = best.pub_status
    m.status_evidence = "; ".join(f"{db}: {st} ({ev})" for db, (st, ev) in statuses.items())
    conflicts = {st for st, _ in statuses.values() if st != "unknown"}
    if len(conflicts) > 1:
        m.signals["status_conflict"] = sorted(conflicts)
    return m

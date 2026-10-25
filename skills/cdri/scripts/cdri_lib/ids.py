"""Canonical identifiers for papers and other entities, plus text normalization."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional

ARXIV_NEW_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")
ARXIV_OLD_RE = re.compile(r"\b([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_RE = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)")


def slug(s: str, n: int = 80) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n] or "item"


def norm_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\\[a-zA-Z]+\s*|[{}$\\]", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def clean_doi(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", d.strip(), flags=re.I)
    while d.endswith(")") and d.count("(") < d.count(")"):
        d = d[:-1]
    d = d.rstrip(".,;:").lower()
    return d or None


def arxiv_from_doi(doi: Optional[str]) -> Optional[str]:
    if doi and doi.lower().startswith("10.48550/arxiv."):
        return doi.split("arxiv.", 1)[1]
    return None


def strip_arxiv_version(a: str) -> str:
    return re.sub(r"v\d+$", "", a)


@dataclass
class PaperID:
    doi: Optional[str] = None
    arxiv: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    openalex: Optional[str] = None
    s2: Optional[str] = None
    url: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def canonical(self) -> str:
        if self.doi and not arxiv_from_doi(self.doi):
            return f"paper:doi:{self.doi.lower()}"
        ax = self.arxiv or arxiv_from_doi(self.doi)
        if ax:
            return f"paper:arxiv:{strip_arxiv_version(ax)}"
        if self.pmid:
            return f"paper:pmid:{self.pmid}"
        if self.pmcid:
            return f"paper:pmcid:{self.pmcid.upper()}"
        if self.openalex:
            return f"paper:openalex:{self.openalex}"
        if self.s2:
            return f"paper:s2:{self.s2}"
        if self.url:
            import hashlib
            return f"paper:url:{hashlib.sha1(self.url.encode()).hexdigest()[:16]}"
        return "paper:unknown"

    def all_ids(self) -> Dict[str, str]:
        out = {k: v for k, v in (("doi", self.doi), ("arxiv", self.arxiv), ("pmid", self.pmid),
                                 ("pmcid", self.pmcid), ("openalex", self.openalex), ("s2", self.s2)) if v}
        out.update(self.extra)
        return out


def parse_identifier(s: str) -> PaperID:
    s = s.strip()
    low = s.lower()
    pid = PaperID()
    for prefix, attr in (("doi:", "doi"), ("arxiv:", "arxiv"), ("pmid:", "pmid"), ("pmcid:", "pmcid"),
                         ("openalex:", "openalex"), ("s2:", "s2")):
        if low.startswith(prefix):
            val = s[len(prefix):].strip()
            if attr == "doi":
                val = clean_doi(val)
                ax = arxiv_from_doi(val)
                if ax:
                    pid.arxiv = ax
                    return pid
            if attr == "pmcid" and not val.upper().startswith("PMC"):
                val = "PMC" + val
            setattr(pid, attr, val.upper() if attr == "pmcid" else val)
            return pid
    if low.startswith("paper:"):
        rest = s[6:]
        kind, _, val = rest.partition(":")
        if kind in ("doi", "arxiv", "pmid", "pmcid", "openalex", "s2"):
            return parse_identifier(f"{kind}:{val}")
    m = re.search(r"arxiv\.org/(?:abs|html|pdf)/([^?\s#]+)", s, re.I)
    if m:
        a = m.group(1).rstrip("/")
        pid.arxiv = a[:-4] if a.lower().endswith(".pdf") else a
        return pid
    m = re.search(r"openalex\.org/(W\d+)", s, re.I)
    if m:
        pid.openalex = m.group(1).upper()
        return pid
    m = re.search(r"(?:/pmc/articles/)(PMC\d+)", s, re.I)
    if m:
        pid.pmcid = m.group(1).upper()
        return pid
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", s)
    if m:
        pid.pmid = m.group(1)
        return pid
    m = DOI_RE.search(s)
    if m:
        d = clean_doi(m.group(0))
        ax = arxiv_from_doi(d)
        if ax:
            pid.arxiv = ax
        else:
            pid.doi = d
        return pid
    m = ARXIV_NEW_RE.fullmatch(s) or ARXIV_OLD_RE.fullmatch(s)
    if m:
        pid.arxiv = m.group(1) + (m.group(2) or "")
        return pid
    m = PMCID_RE.fullmatch(s)
    if m:
        pid.pmcid = m.group(0).upper()
        return pid
    if s.isdigit():
        pid.pmid = s
        return pid
    if re.fullmatch(r"W\d+", s):
        pid.openalex = s
        return pid
    pid.url = s
    return pid


def entity_id(kind: str, label: str) -> str:
    return f"{kind.lower()}:{slug(label)}"


def github_repo(url: str):
    m = GITHUB_RE.search(url or "")
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    name = re.sub(r"\.git$", "", name).rstrip(".")
    return owner, name

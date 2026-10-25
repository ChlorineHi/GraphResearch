"""Normalized bibliographic record shared by all source adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ..ids import PaperID, arxiv_from_doi, clean_doi, strip_arxiv_version

PUB_STATUSES = ("published", "accepted", "preprint", "unknown")


@dataclass
class Record:
    title: str
    source_db: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    date: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    openalex: Optional[str] = None
    s2: Optional[str] = None
    abstract: Optional[str] = None
    citations: Optional[int] = None
    url: Optional[str] = None
    oa_url: Optional[str] = None
    pub_status: str = "unknown"
    status_evidence: str = ""
    types: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    found_by: List[Dict[str, Any]] = field(default_factory=list)
    versions: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.doi = clean_doi(self.doi)
        ax = arxiv_from_doi(self.doi)
        if ax:
            self.arxiv = self.arxiv or ax
            self.doi = None
        if self.arxiv:
            self.arxiv = strip_arxiv_version(self.arxiv)
        if self.title:
            self.title = " ".join(self.title.split())
        if not self.sources:
            self.sources = [self.source_db]

    @property
    def pid(self) -> PaperID:
        return PaperID(doi=self.doi, arxiv=self.arxiv, pmid=self.pmid, pmcid=self.pmcid, openalex=self.openalex,
                       s2=self.s2)

    @property
    def canonical(self) -> str:
        if self.doi or self.arxiv or self.pmid or self.pmcid or self.openalex or self.s2:
            return self.pid.canonical
        from ..ids import slug
        return f"paper:title:{slug(self.title, 60)}-{self.year or 'nd'}"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.canonical
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Record":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**d)


def is_preprint_doi(doi: Optional[str]) -> bool:
    """bioRxiv/medRxiv share the 10.1101 prefix with CSHL journals (e.g. Genome Research 10.1101/gr.*),
    so only the date-style or bare-number suffixes count as preprints."""
    import re
    d = (doi or "").lower()
    if d.startswith("10.1101/"):
        return bool(re.match(r"^10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d+|\d{6,})(v\d+)?$", d))
    return d.startswith(("10.48550/", "10.21203/", "10.20944/", "10.31219/"))

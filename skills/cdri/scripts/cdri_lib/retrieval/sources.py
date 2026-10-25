"""Source adapters. Each `search` returns normalized Records or raises http.HTTPFailure.
Publication status is derived from registry metadata and always carries its evidence string."""

from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional

from .. import config, http
from ..ids import clean_doi
from .records import Record, is_preprint_doi

PREPRINT_VENUES = re.compile(r"arxiv|biorxiv|medrxiv|research square|preprints\.org|ssrn|chemrxiv|osf preprints|"
                             r"openreview", re.I)


def _year(date: Optional[str]) -> Optional[int]:
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def _status_from_venue(venue: Optional[str], doi: Optional[str]) -> tuple:
    if is_preprint_doi(doi):
        return "preprint", f"preprint DOI prefix ({doi})"
    if venue and PREPRINT_VENUES.search(venue):
        return "preprint", f"venue is a preprint server ({venue})"
    if venue and re.search(r"accepted|to appear|in press", venue, re.I):
        return "accepted", f"venue string indicates acceptance ({venue})"
    if venue:
        return "published", f"registry venue: {venue}"
    return "unknown", "no venue information"


# ---------------- OpenAlex ----------------
def _oa_abstract(inv: Optional[dict]) -> Optional[str]:
    if not inv:
        return None
    pos = [(i, w) for w, idx in inv.items() for i in idx]
    return " ".join(w for _, w in sorted(pos))


def openalex_record(w: dict) -> Record:
    ids = w.get("ids") or {}
    prim = w.get("primary_location") or {}
    src = prim.get("source") or {}
    venue = src.get("display_name")
    doi = clean_doi(w.get("doi") or ids.get("doi"))
    wtype = (w.get("type") or "").lower()
    if wtype == "preprint" or src.get("type") == "repository" or is_preprint_doi(doi):
        status, ev = "preprint", f"OpenAlex type={wtype or '?'} source_type={src.get('type')}"
    elif src.get("type") in ("journal", "conference", "book series") or wtype in ("article", "proceedings-article"):
        status, ev = "published", f"OpenAlex primary source {venue!r} (type={src.get('type')})"
        if prim.get("version") == "acceptedVersion":
            status, ev = "accepted", "OpenAlex primary location version=acceptedVersion"
    else:
        status, ev = _status_from_venue(venue, doi)
    versions = []
    for loc in w.get("locations") or []:
        s = loc.get("source") or {}
        if s and s.get("display_name") != venue:
            versions.append({"venue": s.get("display_name"), "type": s.get("type"), "version": loc.get("version"),
                             "url": loc.get("landing_page_url")})
    arxiv = None
    for loc in w.get("locations") or []:
        u = loc.get("landing_page_url") or ""
        m = re.search(r"arxiv\.org/abs/([^v\s]+)", u)
        if m:
            arxiv = m.group(1)
    pmid = (ids.get("pmid") or "").rsplit("/", 1)[-1] or None
    pmcid = (ids.get("pmcid") or "").rsplit("/", 1)[-1] or None
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    return Record(
        title=w.get("title") or w.get("display_name") or "", source_db="openalex",
        authors=[(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])][:50],
        year=w.get("publication_year"), date=w.get("publication_date"), venue=venue, doi=doi, arxiv=arxiv,
        pmid=pmid, pmcid=pmcid.upper() if pmcid else None, openalex=(w.get("id") or "").rsplit("/", 1)[-1] or None,
        abstract=_oa_abstract(w.get("abstract_inverted_index")), citations=w.get("cited_by_count"),
        url=prim.get("landing_page_url") or w.get("id"), oa_url=best.get("pdf_url") or oa.get("oa_url"),
        pub_status=status, status_evidence=ev, types=[wtype] if wtype else [],
        references=[r.rsplit("/", 1)[-1] for r in (w.get("referenced_works") or [])], versions=versions)


OA_SELECT = ("id,doi,title,display_name,publication_year,publication_date,type,primary_location,locations,"
             "cited_by_count,authorships,abstract_inverted_index,open_access,best_oa_location,ids,referenced_works")


def _oa_params(extra: Dict[str, str]) -> str:
    p = dict(extra)
    p["select"] = OA_SELECT
    if config.env("openalex_email"):
        p["mailto"] = config.env("openalex_email")
    return urllib.parse.urlencode(p)


def openalex_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> List[Record]:
    filt = []
    if date_from:
        filt.append(f"from_publication_date:{date_from}")
    if date_to:
        filt.append(f"to_publication_date:{date_to}")
    params = {"search": query, "per-page": str(min(limit, 200))}
    if filt:
        params["filter"] = ",".join(filt)
    data = http.get_json(f"https://api.openalex.org/works?{_oa_params(params)}")
    return [openalex_record(w) for w in data.get("results", [])]


def openalex_work(openalex_or_doi: str) -> Optional[Record]:
    key = openalex_or_doi
    if key.lower().startswith("10."):
        key = f"doi:{key}"
    try:
        w = http.get_json(f"https://api.openalex.org/works/{urllib.parse.quote(key, safe=':/')}?{_oa_params({})}",
                          ttl_days=30)
    except http.HTTPFailure as e:
        if e.status == "not_found":
            return None
        raise
    return openalex_record(w)


def openalex_citing(openalex_id: str, limit: int = 25) -> List[Record]:
    data = http.get_json(f"https://api.openalex.org/works?{_oa_params({'filter': f'cites:{openalex_id}', 'per-page': str(limit), 'sort': 'cited_by_count:desc'})}")
    return [openalex_record(w) for w in data.get("results", [])]


def openalex_by_ids(openalex_ids: List[str]) -> List[Record]:
    out: List[Record] = []
    for i in range(0, len(openalex_ids), 50):
        chunk = "|".join(openalex_ids[i:i + 50])
        data = http.get_json(f"https://api.openalex.org/works?{_oa_params({'filter': f'openalex:{chunk}', 'per-page': '50'})}")
        out += [openalex_record(w) for w in data.get("results", [])]
    return out


# ---------------- Semantic Scholar ----------------
S2_FIELDS = ("title,year,venue,publicationVenue,externalIds,abstract,citationCount,publicationTypes,"
             "publicationDate,openAccessPdf,authors,journal,url")


def _s2_headers() -> Dict[str, str]:
    key = config.env("s2_api_key")
    return {"x-api-key": key} if key else {}


def s2_record(p: dict) -> Record:
    ext = p.get("externalIds") or {}
    venue = (p.get("journal") or {}).get("name") or p.get("venue") or None
    doi = clean_doi(ext.get("DOI"))
    arxiv = ext.get("ArXiv")
    if venue and not PREPRINT_VENUES.search(venue):
        status, ev = "published", f"S2 venue/journal: {venue}"
    elif arxiv and not doi:
        status, ev = "preprint", "S2: arXiv id only, no journal/venue"
    else:
        status, ev = _status_from_venue(venue, doi)
    return Record(
        title=p.get("title") or "", source_db="semantic_scholar",
        authors=[a.get("name", "") for a in (p.get("authors") or [])][:50], year=p.get("year"),
        date=p.get("publicationDate"), venue=venue, doi=doi, arxiv=arxiv, pmid=ext.get("PubMed"),
        pmcid=("PMC" + str(ext["PubMedCentral"])) if ext.get("PubMedCentral") else None, s2=p.get("paperId"),
        abstract=p.get("abstract"), citations=p.get("citationCount"), url=p.get("url"),
        oa_url=(p.get("openAccessPdf") or {}).get("url") or None, pub_status=status, status_evidence=ev,
        types=p.get("publicationTypes") or [])


def s2_search(query: str, limit: int = 20, date_from: Optional[str] = None,
              date_to: Optional[str] = None) -> List[Record]:
    params = {"query": query, "limit": str(min(limit, 100)), "fields": S2_FIELDS}
    if date_from or date_to:
        params["publicationDateOrYear"] = f"{date_from or ''}:{date_to or ''}"
    data = http.get_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params),
                         headers=_s2_headers())
    return [s2_record(p) for p in data.get("data") or []]


def s2_recommendations(paper_ref: str, limit: int = 20) -> List[Record]:
    url = (f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{urllib.parse.quote(paper_ref, safe=':')}"
           f"?limit={limit}&fields={S2_FIELDS}")
    data = http.get_json(url, headers=_s2_headers())
    return [s2_record(p) for p in data.get("recommendedPapers") or []]


# ---------------- Crossref ----------------
def crossref_record(it: dict) -> Record:
    date = None
    for k in ("published-print", "published-online", "issued", "posted", "created"):
        parts = ((it.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            date = "-".join(f"{x:02d}" if i else str(x) for i, x in enumerate(parts))
            break
    ctype = it.get("type", "")
    venue = (it.get("container-title") or [None])[0]
    doi = clean_doi(it.get("DOI"))
    rel = it.get("relation") or {}
    versions = [{"relation": k, "doi": clean_doi(x.get("id"))} for k in ("is-preprint-of", "has-preprint")
                for x in rel.get(k, []) if x.get("id-type") == "doi"]
    if ctype == "posted-content" or is_preprint_doi(doi):
        status, ev = "preprint", f"Crossref type={ctype}"
    elif ctype in ("journal-article", "proceedings-article", "book-chapter"):
        status, ev = "published", f"Crossref type={ctype} in {venue!r}"
    else:
        status, ev = _status_from_venue(venue, doi)
    abstract = re.sub(r"<[^>]+>", " ", it.get("abstract") or "").strip() or None
    return Record(
        title=(it.get("title") or [""])[0], source_db="crossref",
        authors=[f"{a.get('given', '')} {a.get('family', '')}".strip() for a in it.get("author") or []][:50],
        year=_year(date), date=date, venue=venue, doi=doi, abstract=abstract,
        citations=it.get("is-referenced-by-count"), url=it.get("URL"), pub_status=status, status_evidence=ev,
        types=[ctype], versions=versions)


def _cr_mailto() -> str:
    m = config.env("mailto")
    return f"&mailto={urllib.parse.quote(m)}" if m else ""


def crossref_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> List[Record]:
    filt = []
    if date_from:
        filt.append(f"from-pub-date:{date_from}")
    if date_to:
        filt.append(f"until-pub-date:{date_to}")
    params = {"query.bibliographic": query, "rows": str(min(limit, 100))}
    if filt:
        params["filter"] = ",".join(filt)
    data = http.get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params) + _cr_mailto())
    return [crossref_record(it) for it in (data.get("message") or {}).get("items", [])]


def crossref_work(doi: str) -> Optional[Record]:
    try:
        data = http.get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
                             + (_cr_mailto().replace("&", "?", 1)), ttl_days=30)
    except http.HTTPFailure as e:
        if e.status == "not_found":
            return None
        raise
    return crossref_record(data.get("message") or {})


# ---------------- arXiv ----------------
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
STOP = set("a an the of for and or in on to with by from via using towards toward is are under at as its".split())


def _arxiv_query(query: str) -> str:
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    toks = [t for t in re.findall(r"[A-Za-z0-9\-]+", rest) if t.lower() not in STOP and len(t) > 1][:7]
    parts = [f'all:"{p}"' for p in phrases] + [f"all:{t}" for t in toks]
    return " AND ".join(parts) or "all:*"


def arxiv_parse(xml_bytes: bytes) -> List[Record]:
    root = ET.fromstring(xml_bytes)  # noqa: S314 - arXiv Atom feed, no DTD processing
    out = []
    for e in root.findall("a:entry", ATOM):
        aid = (e.findtext("a:id", "", ATOM) or "").rsplit("/abs/", 1)[-1]
        if not aid or "api/errors" in aid:
            continue
        doi = e.findtext("arxiv:doi", None, ATOM)
        jref = e.findtext("arxiv:journal_ref", None, ATOM)
        if jref or doi:
            status = "published"
            ev = f"arXiv metadata journal_ref={jref!r} doi={doi!r} (author-supplied; verify)"
        else:
            status, ev = "preprint", "arXiv entry without journal_ref/DOI"
        pub = e.findtext("a:published", "", ATOM)
        out.append(Record(
            title=e.findtext("a:title", "", ATOM), source_db="arxiv",
            authors=[a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)][:50],
            year=_year(pub), date=pub[:10] if pub else None, venue=jref or "arXiv", doi=doi, arxiv=aid,
            abstract=" ".join((e.findtext("a:summary", "", ATOM) or "").split()), url=f"https://arxiv.org/abs/{aid}",
            oa_url=f"https://arxiv.org/pdf/{aid}", pub_status=status, status_evidence=ev,
            types=[c.get("term") for c in e.findall("a:category", ATOM)]))
    return out


def arxiv_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                 date_to: Optional[str] = None) -> List[Record]:
    q = _arxiv_query(query)
    if date_from or date_to:
        f = (date_from or "1990-01-01").replace("-", "")
        t = (date_to or config.today().isoformat()).replace("-", "")
        q = f"({q}) AND submittedDate:[{f}0000 TO {t}2359]"
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": q, "start": 0, "max_results": min(limit, 100), "sortBy": "relevance"})
    return arxiv_parse(http.get(url, accept="application/atom+xml").body)


def arxiv_by_id(aid: str) -> Optional[Record]:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": aid})
    recs = arxiv_parse(http.get(url, accept="application/atom+xml", ttl_days=30).body)
    return recs[0] if recs else None


# ---------------- PubMed ----------------
def _ncbi(params: Dict[str, str]) -> str:
    key = config.env("ncbi_api_key")
    if key:
        params["api_key"] = key
    return urllib.parse.urlencode(params)


def pubmed_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                  date_to: Optional[str] = None) -> List[Record]:
    p = {"db": "pubmed", "term": query, "retmax": str(min(limit, 100)), "retmode": "json", "sort": "relevance"}
    if date_from or date_to:
        p.update({"datetype": "pdat", "mindate": (date_from or "1900-01-01").replace("-", "/"),
                  "maxdate": (date_to or config.today().isoformat()).replace("-", "/")})
    ids = http.get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + _ncbi(p)) \
        .get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summ = http.get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" +
                         _ncbi({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})).get("result", {})
    out = []
    for i in ids:
        s = summ.get(i) or {}
        aids = {a.get("idtype"): a.get("value") for a in s.get("articleids") or []}
        ptypes = s.get("pubtype") or []
        venue = s.get("fulljournalname") or s.get("source")
        if any("preprint" in t.lower() for t in ptypes):
            status, ev = "preprint", f"PubMed pubtype={ptypes}"
        else:
            status, ev = "published", f"PubMed journal {venue!r} pubtype={ptypes}"
        pmc = aids.get("pmc") or aids.get("pmcid")
        out.append(Record(
            title=s.get("title") or "", source_db="pubmed",
            authors=[a.get("name", "") for a in s.get("authors") or []][:50], year=_year(s.get("sortpubdate")),
            date=(s.get("sortpubdate") or "")[:10].replace("/", "-") or None, venue=venue, doi=aids.get("doi"),
            pmid=i, pmcid=(pmc if (pmc or "").upper().startswith("PMC") else None),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{i}/", pub_status=status, status_evidence=ev, types=ptypes))
    return out


# ---------------- Europe PMC (PubMed + PMC + bioRxiv/medRxiv preprints) ----------------
def europepmc_record(r: dict) -> Record:
    src = r.get("source")
    venue = ((r.get("journalInfo") or {}).get("journal") or {}).get("title")
    if src == "PPR":
        pub = (r.get("bookOrReportDetails") or {}).get("publisher") or "preprint server"
        venue = venue or pub
        status, ev = "preprint", f"Europe PMC source=PPR ({pub})"
    else:
        status, ev = ("published", f"Europe PMC source={src} journal={venue!r}") if venue \
            else _status_from_venue(venue, r.get("doi"))
    oa_url = None
    for u in ((r.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
        if u.get("availabilityCode") in ("OA", "F") and u.get("documentStyle") in ("pdf", "html"):
            oa_url = u.get("url")
            break
    return Record(
        title=r.get("title") or "", source_db="europepmc",
        authors=[a.strip() for a in (r.get("authorString") or "").rstrip(".").split(",") if a.strip()][:50],
        year=int(r["pubYear"]) if str(r.get("pubYear", "")).isdigit() else None,
        date=r.get("firstPublicationDate"), venue=venue, doi=r.get("doi"), pmid=r.get("pmid"),
        pmcid=r.get("pmcid"), abstract=re.sub(r"<[^>]+>", " ", r.get("abstractText") or "").strip() or None,
        citations=r.get("citedByCount"), oa_url=oa_url,
        url=f"https://europepmc.org/article/{src}/{r.get('id')}", pub_status=status, status_evidence=ev,
        types=((r.get("pubTypeList") or {}).get("pubType") or []))


def europepmc_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                     date_to: Optional[str] = None, preprints_only: bool = False) -> List[Record]:
    q = query
    if date_from or date_to:
        q += f" AND FIRST_PDATE:[{date_from or '1900-01-01'} TO {date_to or config.today().isoformat()}]"
    if preprints_only:
        q += " AND SRC:PPR"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": q, "format": "json", "pageSize": str(min(limit, 100)), "resultType": "core"})
    data = http.get_json(url)
    return [europepmc_record(r) for r in (data.get("resultList") or {}).get("result", [])]


# ---------------- DBLP ----------------
def dblp_search(query: str, limit: int = 20, date_from: Optional[str] = None,
                date_to: Optional[str] = None) -> List[Record]:
    url = "https://dblp.org/search/publ/api?" + urllib.parse.urlencode({"q": query, "format": "json",
                                                                        "h": str(min(limit, 100))})
    data = http.get_json(url)
    hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
    out = []
    y0 = _year(date_from)
    for h in hits:
        info = h.get("info") or {}
        au = (info.get("authors") or {}).get("author") or []
        au = au if isinstance(au, list) else [au]
        year = int(info["year"]) if str(info.get("year", "")).isdigit() else None
        if y0 and year and year < y0:
            continue
        typ = info.get("type", "")
        venue = info.get("venue") if isinstance(info.get("venue"), str) else ", ".join(info.get("venue") or [])
        if "Informal" in typ or (venue or "").lower() == "corr":
            status, ev = "preprint", f"DBLP type={typ} venue={venue}"
        else:
            status, ev = "published", f"DBLP type={typ} venue={venue}"
        ee = info.get("ee") if isinstance(info.get("ee"), str) else ((info.get("ee") or [None])[0])
        arxiv = None
        if ee and "arxiv.org/abs/" in ee:
            arxiv = ee.rsplit("/abs/", 1)[-1]
        out.append(Record(
            title=re.sub(r"\.$", "", info.get("title") or ""), source_db="dblp",
            authors=[a.get("text", "") if isinstance(a, dict) else str(a) for a in au][:50], year=year,
            venue=venue, doi=info.get("doi"), arxiv=arxiv, url=info.get("url") or ee, pub_status=status,
            status_evidence=ev, types=[typ]))
    return out


# ---------------- bioRxiv (status / published-version lookup only; the API has no keyword search) ----------------
def biorxiv_published_doi(doi: str) -> Optional[str]:
    for server in ("biorxiv", "medrxiv"):
        try:
            data = http.get_json(f"https://api.biorxiv.org/details/{server}/{doi}", ttl_days=7)
        except http.HTTPFailure:
            continue
        coll = data.get("collection") or []
        if coll:
            pub = coll[-1].get("published")
            return clean_doi(pub) if pub and pub != "NA" else None
    return None


SEARCHERS: Dict[str, Callable[..., List[Record]]] = {
    "openalex": openalex_search, "semantic_scholar": s2_search, "crossref": crossref_search,
    "arxiv": arxiv_search, "pubmed": pubmed_search, "europepmc": europepmc_search, "dblp": dblp_search,
}

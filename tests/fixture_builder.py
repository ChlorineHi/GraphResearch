"""Builds the offline HTTP fixture directory used by the test-suite.

Every record here is SYNTHETIC: titles start with "[SYNTHETIC FIXTURE]", DOIs use the Crossref test prefix
10.5555, arXiv ids use the impossible "9912.*" range and OpenAlex ids use W90000000xx. Nothing in this file
describes a real paper; the fixtures exist only to exercise parsers, routing, dedup and failure logging."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE / "fixtures"
T = "[SYNTHETIC FIXTURE] "

PAPERS = {
    "p1": dict(oa="W9000000001", doi="10.5555/cdri.fx.001", arxiv="9912.00001", date="2026-02-10",
               title=T + "Protein language model features enable binding specificity prediction for unseen "
                         "transcription factors",
               venue="Fixture Journal of Computational Biology", vtype="journal", wtype="article", cites=12,
               refs=["W9000000002"],
               abstract="We predict TF-DNA binding specificity for unseen transcription factors by conditioning a "
                        "sequence model on protein language model embeddings of the DNA-binding domain."),
    "p2": dict(oa="W9000000005", doi="10.1101/2026.03.01.000001", date="2026-03-01",
               title=T + "A biophysical energy model generalizes TF-DNA binding to unseen paralogs",
               venue="bioRxiv", vtype="repository", wtype="preprint", cites=1, refs=[],
               abstract="An additive energy model with an equilibrium occupancy link predicts binding of unseen "
                        "transcription factor paralogs."),
    "p3": dict(oa="W9000000002", doi="10.5555/cdri.fx.003", date="2014-05-02",
               title=T + "Position weight matrices and the biophysics of transcription factor DNA recognition",
               venue="Fixture Reviews in Genomics", vtype="journal", wtype="article", cites=900, refs=[],
               abstract="Foundational treatment of position weight matrices as energy models of TF DNA binding."),
    "p4": dict(oa="W9000000004", doi="10.5555/cdri.fx.004", date="2025-05-20",
               title=T + "Homology leakage inflates reported generalization of TF binding models to unseen proteins",
               venue="Fixture Bioinformatics Letters", vtype="journal", wtype="article", cites=30, refs=[],
               abstract="Benchmark re-evaluation: when train and test transcription factors share DNA-binding "
                        "domain families, unseen-TF performance drops sharply after homology-aware splitting."),
    "p5": dict(oa="W9000000006", doi="10.5555/cdri.fx.005", date="2023-09-12",
               title=T + "Energy-based models of protein-ligand binding with physical priors",
               venue="Fixture Journal of Chemical Physics Methods", vtype="journal", wtype="article", cites=55,
               refs=[], abstract="Statistical physics of binding: Boltzmann occupancy and additive energies."),
    "p6": dict(oa="W9000000007", doi="10.5555/cdri.fx.006", date="2025-08-01",
               title=T + "Contrastive pretraining of TF DNA-binding domains",
               venue=None, vtype=None, wtype="posted-content", cites=3, refs=[],
               abstract="Contrastive objectives over TF families."),
    "p7": dict(oa="W9000000008", doi="10.5555/cdri.fx.007", date="2026-05-30",
               title=T + "Few-shot adaptation of TF binding predictors to unseen transcription factors",
               venue="Fixture Journal of Computational Biology", vtype="journal", wtype="article", cites=0,
               refs=[], abstract="Meta-learning for unseen transcription factor binding prediction."),
}


def _inv(text: str) -> dict:
    inv: dict = {}
    for i, w in enumerate(text.split()):
        inv.setdefault(w, []).append(i)
    return inv


def openalex_work(p: dict) -> dict:
    src = {"display_name": p["venue"], "type": p["vtype"]} if p["venue"] else None
    locs = [{"source": src, "landing_page_url": f"https://doi.org/{p['doi']}", "version": "publishedVersion"}]
    if p.get("arxiv"):
        locs.append({"source": {"display_name": "arXiv (Cornell University)", "type": "repository"},
                     "landing_page_url": f"https://arxiv.org/abs/{p['arxiv']}", "version": "submittedVersion"})
    return {"id": f"https://openalex.org/{p['oa']}", "doi": f"https://doi.org/{p['doi']}", "title": p["title"],
            "display_name": p["title"], "publication_year": int(p["date"][:4]), "publication_date": p["date"],
            "type": p["wtype"], "primary_location": locs[0], "locations": locs, "cited_by_count": p["cites"],
            "authorships": [{"author": {"display_name": "Fixture Author A"}}, {"author": {"display_name": "Fixture Author B"}}],
            "abstract_inverted_index": _inv(p["abstract"]),
            "open_access": {"oa_url": f"https://arxiv.org/pdf/{p['arxiv']}" if p.get("arxiv") else None},
            "best_oa_location": {}, "ids": {"openalex": f"https://openalex.org/{p['oa']}",
                                            "doi": f"https://doi.org/{p['doi']}"},
            "referenced_works": [f"https://openalex.org/{r}" for r in p["refs"]]}


def crossref_item(p: dict, ctype: str) -> dict:
    y, m, d = (int(x) for x in p["date"].split("-"))
    it = {"DOI": p["doi"], "title": [p["title"]], "type": ctype, "container-title": [p["venue"]] if p["venue"] else [],
          "issued": {"date-parts": [[y, m, d]]}, "author": [{"given": "Fixture", "family": "Author A"}],
          "is-referenced-by-count": p["cites"], "URL": f"https://doi.org/{p['doi']}"}
    if p.get("arxiv"):
        it["relation"] = {"has-preprint": [{"id-type": "doi", "id": f"10.48550/arXiv.{p['arxiv']}"}]}
    return it


def arxiv_feed(entries) -> str:
    body = "".join(
        f"""<entry><id>http://arxiv.org/abs/{aid}v2</id><published>{date}T00:00:00Z</published>
<title>{title}</title><summary>{abstract}</summary><author><name>Fixture Author A</name></author>
<category term="q-bio.GN"/></entry>""" for aid, date, title, abstract in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" '
            f'xmlns:arxiv="http://arxiv.org/schemas/atom">{body}</feed>')


def europepmc(records) -> dict:
    return {"resultList": {"result": records}}


def build(dest: Path, variant: str = "initial") -> Path:
    """variant 'initial' = first landscape run; 'refresh' = later state (new paper p7, p6 now published)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    P = PAPERS
    search = [P["p1"], P["p3"], P["p4"], P["p5"]] + ([P["p7"]] if variant == "refresh" else [])
    files = {
        "openalex_search.json": {"results": [openalex_work(p) for p in search]},
        "openalex_work_p1.json": openalex_work(P["p1"]),
        "openalex_refs.json": {"results": [openalex_work(P["p3"])]},
        "openalex_citing.json": {"results": [openalex_work(P["p4"])]},
        "crossref_search.json": {"message": {"items": [
            crossref_item(P["p1"], "journal-article"),
            crossref_item(dict(P["p6"], venue="Fixture Journal of Computational Biology") if variant == "refresh"
                          else P["p6"], "journal-article" if variant == "refresh" else "posted-content")]}},
        "crossref_work_p1.json": {"message": crossref_item(P["p1"], "journal-article")},
        "europepmc_search.json": europepmc([
            {"id": "PPR900001", "source": "PPR", "title": P["p2"]["title"], "doi": P["p2"]["doi"],
             "authorString": "Fixture Author C, Fixture Author D.", "pubYear": "2026",
             "firstPublicationDate": P["p2"]["date"], "abstractText": P["p2"]["abstract"],
             "bookOrReportDetails": {"publisher": "bioRxiv"}},
            {"id": "99000001", "source": "MED", "pmid": "99000001", "title": P["p1"]["title"], "doi": P["p1"]["doi"],
             "authorString": "Fixture Author A, Fixture Author B.", "pubYear": "2026",
             "firstPublicationDate": P["p1"]["date"], "journalInfo": {"journal": {"title": P["p1"]["venue"]}}}]),
        "europepmc_lookup_empty.json": {"resultList": {"result": []}},
        "pubmed_esearch_empty.json": {"esearchresult": {"idlist": []}},
        "biorxiv_details.json": {"collection": [{"doi": P["p2"]["doi"], "published": "NA"}]},
    }
    for name, obj in files.items():
        (dest / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    (dest / "arxiv_search.xml").write_text(arxiv_feed(
        [(P["p1"]["arxiv"], "2025-11-20", P["p1"]["title"], P["p1"]["abstract"])] +
        ([("9912.00009", "2026-06-01", T + "Zero-shot TF binding with structure-aware embeddings",
           "Preprint on unseen transcription factors.")] if variant == "refresh" else [])), encoding="utf-8")
    (dest / "arxiv_empty.xml").write_text(arxiv_feed([]), encoding="utf-8")
    (dest / "arxiv_entry.xml").write_text(arxiv_feed(
        [(P["p1"]["arxiv"], "2025-11-20", P["p1"]["title"], P["p1"]["abstract"])]), encoding="utf-8")
    shutil.copyfile(STATIC / "paper_tfbind.html", dest / "paper_tfbind.html")
    routes = [
        {"match": r"api\.openalex\.org/works\?.*filter=cites:", "file": "openalex_citing.json"},
        {"match": r"api\.openalex\.org/works\?.*filter=openalex:", "file": "openalex_refs.json"},
        {"match": r"api\.openalex\.org/works/doi:10\.5555/cdri\.fx\.001", "file": "openalex_work_p1.json"},
        {"match": r"api\.openalex\.org/works/", "status": 404},
        {"match": r"api\.openalex\.org/works\?", "file": "openalex_search.json"},
        {"match": r"api\.semanticscholar\.org", "status": 429},
        {"match": r"api\.crossref\.org/works/10\.5555/cdri\.fx\.001", "file": "crossref_work_p1.json"},
        {"match": r"api\.crossref\.org/works/10\.", "status": 404},
        {"match": r"api\.crossref\.org/works\?", "file": "crossref_search.json"},
        {"match": r"export\.arxiv\.org/api/query\?.*id_list=9912\.00001", "file": "arxiv_entry.xml"},
        {"match": r"export\.arxiv\.org/api/query\?.*id_list", "file": "arxiv_empty.xml"},
        {"match": r"export\.arxiv\.org/api/query", "file": "arxiv_search.xml"},
        {"match": r"arxiv\.org/html/9912\.00001", "file": "paper_tfbind.html", "content_type": "text/html"},
        {"match": r"arxiv\.org/(html|pdf)/", "status": 404},
        {"match": r"ebi\.ac\.uk/europepmc/webservices/rest/search\?.*resultType=lite", "file": "europepmc_lookup_empty.json"},
        {"match": r"ebi\.ac\.uk/europepmc/webservices/rest/search", "file": "europepmc_search.json"},
        {"match": r"ebi\.ac\.uk/europepmc/.*fullTextXML", "status": 404},
        {"match": r"eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/esearch", "file": "pubmed_esearch_empty.json"},
        {"match": r"api\.biorxiv\.org/details", "file": "biorxiv_details.json"},
        # dblp.org intentionally unmatched -> logged as 'offline' (exercises failure reporting)
    ]
    (dest / "routes.json").write_text(json.dumps(routes, indent=1), encoding="utf-8")
    return dest

# Retrieval strategy

## Sources (adapters in `cdri_lib/retrieval/sources.py`)

| id | covers | key / etiquette |
|---|---|---|
| openalex | all fields, citations, OA locations, references | `OPENALEX_EMAIL` or `CDRI_MAILTO` (polite pool) |
| crossref | DOI registry, types (journal-article vs posted-content), relations | `CDRI_MAILTO` |
| semantic_scholar | CS/biomed search, recommendations | `S2_API_KEY` (without it 429 is common) |
| arxiv | preprints (CS, physics, math, q-bio, stat) | none; 3 s throttle |
| pubmed | biomedical literature | `NCBI_API_KEY` optional |
| europepmc | PubMed + PMC + bioRxiv/medRxiv preprints (SRC:PPR), OA full-text XML | none |
| dblp | CS venues | none |
| bioRxiv API | published-version lookup for 10.1101 DOIs (no keyword search) | none |

Discipline routing (`assets/disciplines.json`) picks sources from detected disciplines; add `--source` to restrict.
Publisher pages are only reached through OA locations (OpenAlex/Unpaywall); no scraping behind paywalls.

## Lanes

- **in_domain**: topic + variants (core window) + recent preprints (life science) + foundational (no floor).
- **adjacent**: agent abstractions + problem-structure abstract queries + adjacent fields of the structure.
- **distant**: mechanisms suggested by the structure (or `--mechanism`, `--use-kg`) in fields other than the home
  discipline, phrased by mechanism, e.g. "optimal transport unpaired distributions" - not topic keywords.
- **contradictory**: assumption probes, failure modes, re-evaluations, benchmark leakage critiques.

## Windows

`today` (override with `CDRI_TODAY` for reproducible tests), `recent_from = today - window_months` (default 24),
`core_from = today - core_years` (default 5). Change via `config set window_months 12`.

## Dedup and status

Union-find over identifiers + title similarity ≥ 0.93 (year gap ≤ 2 for preprints). The published record wins;
preprints are kept as `versions` (`preprint_version`). Status evidence is recorded (e.g. "Crossref
type=posted-content"). arXiv `journal_ref` is author-supplied → stated as such. `paper verify` re-checks a DOI
against Crossref/OpenAlex and title similarity (flags `not_found` / `title_mismatch`).

## Logging and failures

Each (query × source) attempt is a line in `runs/<id>/log.jsonl` with status `ok | empty | rate_limited |
error | offline | blocked_privacy | skipped`. `summary.json` aggregates by source/lane and lists failures.
HTTP responses are cached in `$CDRI_HOME/cache/http` (7-day TTL; 30 for single works). `CDRI_OFFLINE=1`
uses cache only. Secrets in URLs are redacted in logs.

## Privacy gate

Queries that look like local paths, tokens, long hex strings, e-mails or > 300 characters are not sent
(`blocked_privacy`) unless `--allow-sensitive` is given with the user's consent.

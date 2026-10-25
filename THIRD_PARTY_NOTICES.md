# Third-party notices

CDRI was designed after studying four MIT-licensed research skill repositories (analysis in
`docs/01-reference-analysis.md`). **No source files were copied**; the ideas and algorithms listed below were
re-implemented against CDRI's own data model. Credit and license notices:

| Project | License | What CDRI re-implements / adapts |
|---|---|---|
| [marciob/skill-research-papers](https://github.com/marciob/skill-research-papers) | MIT (© 2026) | Identifier regexes, legal open-access full-text cascade order, HTML stub detection, read plan + end-of-paper sentinel for verifying a complete read |
| [KalarisLabs/research-agent-skills](https://github.com/KalarisLabs/research-agent-skills) | MIT | SQLite FTS5 + BM25 chunk index with section headings; citation verification heuristics (title-similarity thresholds, year tolerance, arXiv fallback); epistemic labels and "no single winner" principle for ideation; GraphML / node-link JSON export formats as reference |
| [pinshuai/literature-review-skill](https://github.com/pinshuai/literature-review-skill) | MIT (© 2024 K-Dense Inc.) | Search-log fields and recorded inclusion/exclusion reasons (structured here as JSONL) |
| [jxtse/scientific-research-skills](https://github.com/jxtse/scientific-research-skills) | MIT (© 2026 Richard Tse) | DOI-prefix → publisher routing notes and text-and-data-mining compliance notes (browser-login scraping is **not** reused) |

The MIT License requires the copyright notice to accompany copies of substantial portions of the software;
since no code was copied this is a courtesy attribution. The reference checkouts live in `_refs/` for analysis
only and are excluded from the distributable skill (`.gitignore`, installer copies only `skills/cdri/`).

## External services

CDRI calls public scholarly APIs when the agent runs a command: OpenAlex, Crossref, Semantic Scholar,
arXiv, NCBI E-utilities (PubMed), Europe PMC, bioRxiv/medRxiv API, Unpaywall, dblp, GitHub. Their terms of use
apply. CDRI identifies itself with a User-Agent and (if configured) a contact e-mail, honours rate limits and
`Retry-After`, and only downloads legal open-access full text.

## Optional Python packages (not bundled)

PyMuPDF / pymupdf4llm (AGPL-3.0 / commercial — note the license if you redistribute), pypdf (BSD),
sentence-transformers (Apache-2.0). CDRI works without them using the standard library.

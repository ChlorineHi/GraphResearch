# Epistemic status, provenance and knowledge layers

## Statuses (low → high support)

| status | report label | granted when |
|---|---|---|
| unverified | Unsupported / Unverified | default; any requested status the evidence cannot support |
| hypothesis | Hypothesis | agent proposals: transfer hypotheses, ideas, agent-proposed limitations |
| agent_inference | Agent Interpretation | agent analysis (signatures, inferred limitations, mechanism links) |
| user_reported | Agent Interpretation (user-reported) | statements from the user, experiments without artifact |
| author_claim | Author Claim | paper_fulltext/supplement source **and** the cited location is in the reading ledger |
| verified | Verified Fact | registry metadata (DOI, dates, venue) from OpenAlex/Crossref/arXiv/PubMed/Europe PMC |
| code_verified | Verified Fact (code) | `code` source with pinned commit + file location |
| experiment_observed | Verified Fact (local experiment) | `local_experiment` source with an existing artifact file |
| vocabulary | (ontology term) | mechanisms, assumptions, datasets, metrics as names - not claims |

Rules enforced by the CLI:
- Status is granted from provenance, never from the request alone. The agent cannot self-certify.
- Existing statuses are **never upgraded automatically**. New supporting evidence is stored as provenance and
  shows up in `kg pending`; promotion is explicit (`kg promote`) and logged.
- Method details (formulation, innovation, implementation) sourced from abstract/introduction → unverified.
- `CONTRADICTS` edges mark both endpoints `contested`; nothing is deleted. `kg retract` hides with a reason.
- Every write appends provenance: source_type, source_ref, location (section/page/equation/file:lines),
  quote (≤500 chars), commit, extractor, timestamp, requested and granted status.

## Layers

- **Global KB** (`$CDRI_HOME/global.sqlite`): papers, methods, mechanisms, signatures, claims, limitations,
  transfer hypotheses, abstract problem signatures shared by projects, reading ledger, full-text chunk index.
- **Project KB** (`<project>/.cdri/project.sqlite`): Project, LocalExperiment, Diagnosis, FailureMode,
  project ideas, interpretations of local results.
- **Link layer**: edges touching a project node live in the project store (e.g. an experiment that
  CONTRADICTS a global claim). Other projects see the global claim (marked contested) but not the local data.

## Entity normalization and versions

Canonical paper id: DOI > arXiv > PMID > PMCID > OpenAlex > S2. arXiv DOIs (10.48550) map to arXiv ids,
versions are stripped. Preprint and published versions are linked with `VERSION_OF`; publication status keeps
its evidence string and a status_history when it changes. Mechanisms resolve through ontology aliases
(e.g. Sinkhorn → entropic-optimal-transport); unknown ones are stored as discovered `agent_inference` nodes.

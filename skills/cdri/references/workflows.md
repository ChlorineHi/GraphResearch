# CDRI workflows by mode

`$CDRI` = `python <skill dir>/scripts/cdri.py`. Every step that writes knowledge goes through the CLI.

## Contents
- landscape · paper · compare · graph · ideate · story · refresh
- transfer → transfer.md · diagnose → diagnosis.md · audit → integrity-audit.md

## landscape

Goal: a layered, honest map of a topic, including adjacent fields, distant fields with the same mathematical
structure, and contradicting evidence.

1. `kg search "<topic>" --mode semantic` - what is already known (avoid re-reading).
2. Write 1-3 **abstract problem statements** that strip domain words (e.g. "predict interactions for entities
   unseen in training, given descriptors"). Pick structures: `$CDRI ontology structures`.
3. `landscape plan "<topic>" --variant "<synonym>" --abstraction "<abstract>" --structure <id>
   [--mechanism <id>] [--assumption <id>] [--method "<name>"] [--intensity quick|standard|deep] [--use-kg]
   --out plan.json`. Review: are distant queries driven by mechanisms (not by topic keywords)? Does the
   contradictory lane probe assumptions, benchmark leakage and failure modes? Edit plan.json if needed.
4. `landscape run --plan plan.json` → summary with per-database status counts and `failures`.
   If a source failed (`rate_limited`, `offline`, `error`), retry later or report it - never hide it.
5. `screen suggest --run <id> --tier focused` then `screen decide ... --reason`. Tiers: landscape (metadata),
   focused (abstract + key sections), deep (full text + code). No fixed counts: stop when new papers stop
   changing the picture. Optional: `cite expand <doi> --direction both` for key papers (OpenAlex).
6. For deep papers follow **paper**.
7. `report landscape --run <id> --out auto` and fill the AGENT sections: scientific questions, paradigms,
   method taxonomy, recent vs foundational, controversies (cite contradictory-lane evidence), limitations
   (author-acknowledged vs inferred vs agent-proposed).

## paper

1. `paper fetch <id>`; if `unavailable`, report the attempts and either ask the user for a legal local copy
   (`--file`) or continue at abstract level and label everything accordingly.
2. `paper read <id>` → read every read_plan chunk with your file reader; the parsed text starts with an
   UNTRUSTED marker and ends with `<!-- END-OF-PAPER:<hash> -->`. Then `paper confirm <id> <hash>`.
   For targeted reading use `paper section <id> methods|results|"3.2"|Supplementary`.
3. Code: `code locate <id>` (links found in the paper text only). Confirm the repo is official (paper or
   authors' page). `code analyze <repo> --commit <sha>` → roles (model / loss / dataset / train_loop /
   evaluation / preprocessing / config_cli), hyperparameter defaults, permalinks. Read the actual code with
   `code show`. Map each key equation to a function; mark `discrepancy` when code differs from the paper.
4. Fill the card (paper-card.md), `paper validate`, fix warnings you can fix honestly, `paper ingest`.
5. `report paper --id <id>` and complete "与其他方法的本质差别".

## compare

1. Ensure both methods have signatures (`signature show method:<x>`; add with `signature add`).
2. `compare methods method:a method:b` → facet table (mechanisms, structures, data, supervision, operators,
   assumptions, invariances, biases) + assumption differences.
3. For numbers: `audit compare --results results.json` (protocol per result). Rank only inside comparable groups.
4. Write: what problem each solves, which assumptions differ, why results may differ (protocol vs method).

## graph

- Reuse: `kg search "<q>" --mode keyword|semantic|mechanism|chunks|graph`; `kg show <id>` (node, edges,
  provenance, reading ledger).
- Visualize: `graph export --view citation|mechanism|transfer|problem-limitation|evidence --format
  mermaid|dot|html|graphml|json [--focus <id> --depth 2] --out file`.
- Lineage of an idea / transfer hypothesis / failure: `graph lineage <id> [--format mermaid]`.
- Coverage and gaps: `graph coverage [--topic "<q>"]` (reading depth, recency, single-domain mechanisms,
  problems without methods).
- Maintenance: `kg pending` (statuses supported by newer evidence) → `kg promote <id> --status ... --source-type
  ... --ref ... --location ...`; `kg retract <id> --reason`; `kg contradictions`.

## ideate

1. Start from evidence: a transfer hypothesis, a failure mode, a contradiction or a gap from `graph coverage`.
2. `ideate scaffold [--from transfer:<id>]` → fill: question, sources (KB ids), shared_structure,
   mechanism_hypothesis, distinction_from_prior, falsifiable_predictions (each with refuted_if), risks.fails_if,
   evidence.existing / evidence.missing, innovation_type, source_domains, dimensions (level + rationale each).
3. `ideate add idea.json` - stored as Hypothesis with lineage edges. Cards with a single score are rejected.
   "method_combination" alone triggers a warning: explain the new inductive bias / problem definition.
4. Respect frozen decisions (`project show`); the card must state `respects_frozen_decisions`.

## story

1. Record what actually happened: `experiment record` (artifacts!), `diagnose conclude`, counterexamples via
   `kg link <experiment> CONTRADICTS <claim> --status experiment_observed --source-type local_experiment
   --artifact <file>`.
2. `story scaffold` → candidates per arc step: Important Question → Unexpected Observation / Gap →
   Mechanistic Insight → Novel Approach → Critical Evidence → Implication → Boundary Conditions.
3. Draft story.json (template in scaffold output); `story check story.json` - fails if established claims
   rest on hypotheses, proof/causal language lacks evidence, or alternatives/limitations are missing.
4. Write the narrative. Negative results, noise ceilings, identifiability limits and counterexamples are valid
   contributions; never present a hypothesis as a finding.

## refresh

- `refresh add "<topic>" [--structure ...]` registers a watch; `refresh run <id>|--all [--since DATE]` searches
  only from the last successful check, lists new papers and preprint→published changes, and does not advance
  the checkpoint if every source failed. Nothing runs in the background: refresh happens only when invoked.

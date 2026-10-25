# Cross-domain mechanism transfer

## Method Signature (F_signature or `signature add method:<id> sig.json`)

`source_domain, original_problem, mathematical_abstraction, core_operators[], mechanisms[], inductive_biases[],
required_assumptions[], data_structure[], supervision[], invariances[], complexity, generalization_mechanism,
failure_conditions[], potential_target_domains[], problem_structures[]`.
Mechanisms and structures resolve against `assets/mechanisms.json` / `assets/problem_structures.json`
(`$CDRI ontology mechanisms --id optimal-transport`). Unknown mechanisms become discovered nodes
(agent_inference), so the ontology grows but never silently.

## Matching (structure, not vocabulary)

`compare` / `transfer scan` compute weighted Jaccard per facet: mechanisms 0.22 (ancestors count 0.5),
problem_structures 0.20, data_structure 0.14, supervision 0.10, core_operators 0.10, required_assumptions 0.10,
invariances 0.08, inductive_biases 0.06; plus lexical similarity of problem descriptions as a contrast.
Flags: `lexical_only` (shared words, little structure → not transferable), `structural_bridge`,
`same_domain`, `low_facet_coverage`, `no_new_mechanism`. The number is a retrieval aid, not a prediction.

## Problem-driven (`transfer scan`)

1. `project problem problem.json` with the abstract problem signature (no data) - mirrored to the Global KB so
   other projects can find it (use `--local-only` to keep it private).
2. Make sure candidate methods have signatures (from paper cards or `signature add`). If few exist, run a
   landscape with the distant lane first and ingest cards for promising papers.
3. `transfer scan` → candidates with `new_mechanisms_for_target` (the mechanism difference is the opportunity).
4. Record facts about the target: `project fact <assumption-id> true|false|unknown --note "..."`.
5. `transfer check method:<id>` → assumptions satisfied/violated/unknown (method + mechanism typical
   assumptions), failure conditions, negative-transfer risks (assumption_violated, failure_condition_present,
   supervision_mismatch, data_structure_mismatch, scale_check), unknowns to check.
6. `transfer prior --mechanism <id> --domain <target>` → KB hits + queries to check whether the transfer already
   exists (absence in the KB is not novelty).
7. `transfer record method:<id> [--rationale ...]` → TransferHypothesis (status hypothesis) with lineage.

## Method-driven

`transfer scan --method method:<id>` compares a method against all open problem signatures registered by any
project.

## Reasoning you must write

For each candidate: source problem and mechanism; why the target shares the structure (facets); which
assumptions hold / fail / are unknown; what must be redefined (cost, supervision, representation); expected
benefit and how it would be tested; negative-transfer risk; why this is not just component stacking (new
inductive bias / problem definition / evaluation). Then `ideate scaffold --from transfer:<id>`.

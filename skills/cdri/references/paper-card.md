# Paper card (method-level record)

Template: `$CDRI paper card-template`. Every item carries `source: {type, location, quote?, commit?}` with type
`paper_fulltext | paper_supplement | paper_abstract | code | agent`. Delete fields you cannot fill; gaps are
reported, guesses are not acceptable.

## Sections

- **A_question**: problem (with id), importance, prior_limitations, what_changed (problem_definition /
  model_mechanism / training_objective / data_usage / evaluation).
- **B_formulation**: inputs, outputs, supervision, objective, assumptions (use ontology ids where possible, e.g.
  `equilibrium-or-quasi-equilibrium`), operators, equations (label, latex, role, depends_on, location).
- **C_innovation[]**: statement, kind (structure | objective | probabilistic | representation | inference |
  paradigm), novel_vs_prior (required for standard components), prior_work (ids), inductive_bias, why_fits, scope.
- **D_implementation**: repo {url, commit (full SHA), official, location of the code statement}, items
  (tensor_shapes, preprocessing, sample_construction, loss_computation, train_vs_infer, hyperparameters,
  modules) with code sources, code_links [{formula, path, symbol, lines, permalink, status, note}].
- **E_evidence**: experiments (hypothesis_tested, result, is_ablation, is_ood, datasets, metrics, protocol),
  negative_results, limitations {author_acknowledged (paper source), inferred_from_results (basis),
  agent_proposed (rationale)}.
- **F_signature**: see transfer.md.
- **G_research_story** (selected innovative papers only): see [research-story.md](research-story.md).
  Records selection scope/reason, the scientific argument with source locations, contributions beyond SOTA,
  a no-SOTA counterfactual, alternative explanations and conditional lessons. Delete when not performed.

## What the CLI enforces at validate/ingest

- reading_depth fulltext/deep needs ledger entries; deep needs a Methods-kind section read → else downgraded.
- B/C/D items from abstract/introduction → unverified; items without source → unverified.
- Standard components (transformer, GNN, attention, diffusion, contrastive, ...) without novel_vs_prior → warning,
  unverified.
- code_links `consistent`/`discrepancy` need repo.commit and path, else → unverified. Code evidence with commit
  and location → code_verified.
- author_acknowledged limitations without a paper source move to agent_proposed. Inferred → agent_inference;
  agent_proposed → hypothesis.
- Paper-sourced items whose location is not in the reading ledger are stored as unverified with a warning. After
  reading more, re-ingest; supported upgrades appear in `kg pending` and require `kg promote`.
- G is stored as a separate, searchable ScientificClaim linked to the paper and method, with `source_type=agent`.
  Complete, ledger-backed analyses are `agent_inference`; missing/unread evidence stays `unverified`. Neither
  a paper citation nor a user-supplied status can make this interpretation an Author Claim or Verified Fact.
  Ingestion returns `research_story_id`; `report paper` includes the analysis. Older A-F cards remain valid.

## Reading ledger

`paper section` records each covered section (mode cli_read). `paper confirm <id> <hash>` records the whole
paper (mode sentinel_confirmed) and is only valid with the END-OF-PAPER hash of the cached text. The ledger is
global, so other projects can see what was read and reuse cards instead of re-parsing.

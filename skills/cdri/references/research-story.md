# Research-story understanding and retrieval

Use when an innovative candidate emerges during literature review or deep reading, or when the user asks how
a paper builds a compelling scientific contribution. The result is a reusable understanding of the argument,
stored with the paper for retrieval during research-thesis development, ideation, diagnosis and writing.

## Choose and read

- Explain why this paper deserves deeper analysis: reframing a consequential question, exposing an assumption,
  resolving a contradiction, a new mechanism/theory, an informative evaluation, a counterexample, a resource,
  or a useful explanation of failure. Measured improvements can support these contributions too.
- Interpret "most innovative" relative to the papers actually retrieved and read. Record comparison paper IDs,
  search coverage and unresolved prior-work checks. Search rank, novelty claims, citations, prestige and SOTA
  alone cannot decide this. For `quick`, keep the candidate set small; do not inflate a quota of novel papers.
- Read Introduction/Related Work, Methods/theory, Results, Discussion/Limitations and relevant supplementary
  evidence. Abstract-only selection is provisional: do not reconstruct unseen ablations or a complete story.
  Existing reading-ledger rules apply. Claims about prior work need that work checked or remain author claims.

## Analyze the scientific argument

"Good story" means a coherent, consequential, evidence-supported argument. Extract these seven steps into
`G_research_story.arc`; each step has `text` and `evidence: [{location, role}]`:

1. **important_question**: why answering this question changes scientific understanding or useful practice;
   who/what is affected and what existing framing misses.
2. **observation_or_gap**: the specific puzzle, contradiction, failure or unmet capability; distinguish a
   demonstrated gap from an assertion that nobody has tried a component combination.
3. **mechanistic_insight**: the conceptual move that changes how to understand the puzzle. Mark an author's
   proposed explanation as proposed when evidence cannot distinguish it from alternatives.
4. **approach**: how the method, theorem, data or evaluation follows from that insight; what assumptions or
   inductive biases make it a reasoned design choice.
5. **critical_evidence**: which figure, table, theorem, intervention, ablation or case is load-bearing; which
   claim it tests, what competing explanation it excludes, and what it does not exclude. Reference figure/table
   IDs in `role` and a read section in `location`; a leaderboard rarely tests the whole mechanism.
6. **scientific_implication**: what readers can now explain, predict, measure or do; how far the evidence allows
   that conclusion and what contribution survives independent of ranking.
7. **boundary_conditions**: assumptions, domains, negative results, costs, counterexamples and uncertainty that
   constrain the story. Missing limitations are a gap, not proof of broad applicability.

Also fill:

- `summary`: a compact argument joining question → insight → decisive evidence → implication.
- `selection_reason` and `comparison_scope`: why selected and the verified/known IDs compared; use an explicit
  "single-paper analysis; novelty not compared" entry when no comparison was done. Do not invent prior-work IDs.
- `contribution_types`: meaningful types such as problem_definition, theoretical_framework, inductive_bias,
  mechanistic_understanding, benchmark_or_evaluation, counterexample, noise_ceiling_or_identifiability,
  failure_explanation, cross_domain_concept or dataset/resource.
- `beyond_sota`: substantive contribution and evidence beyond the numerical gain. If the gain is the only
  supported contribution, say so rather than inventing a mechanism or a deeper thesis.
- `counterfactual_without_sota`: if the headline improvement vanished, what contribution and supporting
  evidence would remain? This is an analytical counterfactual, not a new experimental result. A new capability
  may depend on performance; acknowledge that rather than discounting necessary empirical success.
- `alternative_explanations`: strongest rival explanations, unresolved controls and weaknesses. Distinguish
  elegance/persuasiveness from actual evidential strength and consider negative or contradicting papers.
- `transferable_lessons`: conditional lessons with `lesson`, `conditions`, `misuse_risk`: question formation,
  conceptual reframing, evidence design, and matching a claim's breadth to its support. Avoid copying rhetorical
  wording or implying that a successful story pattern guarantees publication.

State **Agent Interpretation** for this synthesis. Keep the authors' claims in the normal A-F evidence items.
Actual editorial/acceptance reasons are unknown unless explicit editorial/reviewer evidence is supplied and
verified; observed publication is not proof that our explanation caused acceptance. Preprints can have strong
arguments too. Do not invent reviewer preferences or make prestige a validation signal.

## Store a retrievable understanding card

`paper card-template` includes optional G. Fill it only when this analysis was performed, then use
`paper validate card.json` and `paper ingest card.json`. The ordinary A-F-only workflow remains supported.

Ingestion returns `research_story_id` and stores a ScientificClaim with `claim_type=research_story`, linked via
`LINKS_TO` from the paper and method. The full G content is included in `rationale` for keyword/semantic
retrieval, with source paper ID, evidence locations and explicit gaps. Its provenance is always `agent`:
complete ledger-backed analyses remain `agent_inference`; incomplete/unread ones are `unverified`. The CLI
checks structure and ledger coverage, not whether an interpretation or novelty judgment is correct.
After adding missing evidence, validate and re-ingest. Existing statuses do not auto-upgrade; if validation
now supports `agent_inference`, explicitly use `kg promote <research-story-id> --status agent_inference
--source-type agent --ref <paper-id> --location "<newly read evidence locations>"`. Agent-sourced interpretations
do not appear in the current `kg pending` evidence filter. Repeated retrieval does not strengthen the evidence
status. `report paper --id <paper-id>` displays the stored understanding.

These literature cards are global and reusable across projects. Do not put unpublished project data, local run
paths or new project-specific thesis proposals in G. Keep those in the project layer and link to the paper/card
IDs, consistent with [experiment-history.md](experiment-history.md).

## Retrieve to improve a research thesis

Before ideation or scientific storytelling, formulate a few focused queries from the current question:
the scientific problem, a possible mechanism, an analogous contradiction, and the discriminating evidence
needed (for example, "identifiability counterexample ranking supervision" rather than only a domain name).

```bash
$CDRI kg search "<problem, insight or evidence-design pattern>" --mode semantic --type ScientificClaim
$CDRI kg search "<distinctive term>" --mode keyword --type ScientificClaim
$CDRI kg show <research-story-id>
$CDRI kg show <source-paper-id>
```

Inspect `claim_type=research_story`, provenance, reading depth, publication status and source locations.
Open the original evidence when a summary is too coarse or contested; use `paper section` only for sections
actually read. Semantic relevance scores are retrieval aids, not scientific merit scores.

Use each relevant card as question/insight/evidence scaffolding. Explicitly state which principle transfers,
why the current problem meets its conditions, which assumptions fail, and what our own evidence still lacks.
Generate a falsifiable research thesis with the minimal experiment or theoretical check that could distinguish
it from alternatives. Keep the new application **Hypothesis** until tested; never cite another paper's successful
story as evidence for our result. Link the source understanding card/paper IDs in the idea's `sources`.

Report the chosen paper's argument, value without SOTA, weaknesses, conditional lessons and stored/retrieved
IDs. If no suitable card is found, report the retrieval gap and reason from available evidence; do not claim
RAG enrichment happened without actually retrieving and inspecting records.

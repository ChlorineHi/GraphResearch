# Optional learning from past experiments

Use before the selected research workflow when local experiments can inform the question. The agent reads
artifacts and reasons about them; existing CLI commands record evidence and interpretations. There is no
automatic folder-ingestion CLI or guarantee of understanding every log format. Read this reference only
when considering or performing history learning.

## Selection and scope

`learn_history` is an instruction-level option, accepted through natural language or a request field:

- `on`: the user asks to review/learn from past experiments. Use the supplied `history_root` or clearly
  identified experiment folder in the current project. If the location is genuinely missing, ask for the path
  while continuing independent work; never imply the requested review has happened.
- `off`: the user asks to skip history. Do not inventory folders or read past-run artifacts for this step.
  Normal literature/KB work may continue; do not silently re-enable history during diagnosis.
- `auto` (default): use history when it bears on the current model, dataset, failure or research goal and the
  current project has clearly identifiable experiment folders. Otherwise skip. Do not ask a blocking question
  just to choose this optional step, and do not browse unrelated folders to find something to review.

Explicit user choices override `auto`. Useful optional fields are `history_root`, `include`, `exclude` and
`focus_metrics`; they are agent instructions, not CLI flags. Announce the chosen scope briefly. Use the same
selection on session resume unless the user changes it. Record choice, roots and coverage with `session note`.
Reading another supplied project's artifacts does not change the destination project: use `--project` for
the current research project on every recording command.

## Inventory and select evidence

1. List files with `rg --files <history_root>` (or the available file-listing tool). Focus on result summaries,
   logs, configurations, saved code snapshots, run manifests, evaluation scripts and notebook code/output.
   Common candidates include `experiments/`, `runs/`, `results/`, `logs/` and `checkpoints/`; directory names
   alone do not establish that a model was trained. Inspect hidden/ignored run files only within the selected
   experiment scope when necessary. Exclude environments, dependencies, caches and generated review outputs.
2. Select representative baselines, model variants, ablations, best and typical runs, failures and null results.
   Prefer relevance and controlled comparisons over reading every file. State selection criteria and omitted
   runs; never call a sample exhaustive. A selected run is evidence only after its actual contents are read.
3. Keep source artifacts unchanged. Do not run/import training or evaluation code, execute notebooks, install
   dependencies or deserialize model checkpoints (`pickle`, `.pt`, `.pth`, etc.). Read notebook JSON as data.
   For unsupported binary logs, use available safe local readers or accompanying text exports; otherwise mark
   metrics unavailable. Do not silently download a parser or fetch remote experiment-tracker data.

## Build an evidence card for each run

Capture available fields, with `unknown` for missing facts rather than inferred defaults:

- Identity: source root, run ID, timestamp, completion/failure state, seed, fold and relationship to variants.
- Task/data: dataset and version, preprocessing, split and split unit, training size, test-time information,
  pretraining resources and leakage checks.
- Metrics: original name, canonical metric if known, value, direction, units/scale, train/validation/test,
  aggregation, subgroup, epoch/checkpoint, selection rule, seed count and reported variance/interval.
  Preserve original values and exact file/row/JSON key/output-cell locations. Missing, NaN and failed results
  are not zero. Distinguish the last epoch, best validation checkpoint and its corresponding test result;
  do not select the best test epoch or treat repeated evaluations of one checkpoint as independent runs.
- Code/config: model architecture, key modules, inputs/outputs, loss, optimizer/schedule, relevant hyperparameters,
  evaluation/metric implementation and resource costs if measured. Cite file/function/line locations.
- Run-to-code link: saved snapshot or commit, config, dirty-worktree status if known, and confidence in the link.
  Trace manifest → config → instantiated model → training objective → evaluation → result. A current `model.py`
  or Git HEAD may differ from the historical run. Label it `current code only; historical implementation
  unverified` unless run-specific evidence ties them together; never substitute current code for a missing snapshot.

Use `code analyze <local-path>` and `code show <local-path> <file> --symbol <symbol>` as static reading aids
when useful; direct file reading handles unsupported languages or layouts. Local analysis does not check out
the requested historical commit. Record a file hash when no commit is available; a hash identifies a snapshot
but does not establish that it produced a run. Static architecture properties are not measured performance.

## Compare and extract knowledge

Prepare `results.json` as `{"results": [...]}` for `audit compare --results results.json`. Each result has a
unique `id`, `source`, `model`, `metric`, `value` and `protocol`. Use the protocol fields in
`assets/metric_ontology.json` (`comparability_fields` plus metric-specific `must_specify`); unresolved fields
must be omitted or JSON `null`, never identical `"unknown"` strings that could be mistaken for a match.

- Compare only matched metrics and protocols; differences → **Not Directly Comparable**, missing information
  → **Unknown Comparability**. Also inspect checkpoint selection, fold membership, metric scale and evaluation
  code: the CLI cannot validate facts the agent has not supplied. For unknown/custom metrics, establish their
  definition and direction manually before interpreting a ranking. Never combine different metrics into one score.
- Separate observed performance from attribution. A larger model with a higher score does not show which module
  helped. Use controlled ablations and comparable training/tuning budgets, report seed variation, and name
  confounders such as changed data, supervision, pretraining or evaluation. Do not claim significance from one run.
- For each model, explain **strengths**, **weaknesses/failure conditions**, **supporting and opposing evidence**,
  **possible mechanism**, and **what is worth retaining or changing**. Missing evidence means unknown, not a
  demonstrated weakness. Include negative runs and subgroup regressions, not just winners.
- Distill conditional lessons: **observation → interpretation → applicability/boundaries → counterevidence →
  next discriminating experiment**. Keep metric observations `experiment_observed` only when backed by read
  source artifacts, causal/mechanistic explanations `agent_inference`, and untested improvements `hypothesis`.
  The existence of a file alone does not substantiate all claims stored beside it. No automatic retraining.

## Persist through existing CLI commands

Keep source runs and their lessons in the **current project KB**. Do not create global Method, CodeModule or
ScientificClaim nodes containing local code, paths or experimental results; generic `kg node` routes those
types globally on first creation. The following existing path keeps the interpretation project-local:

1. Check `experiment list` and `kg show <id>` before recording. Choose a unique name using the source project,
   relative run path/run ID and a short artifact hash (early in the name; experiment IDs are truncated slugs).
   Reuse unchanged records; give changed artifacts new versioned names rather than overwriting prior evidence.
2. For a run with known outcome relative to a stated baseline/goal, write evidence cards into `--config`
   and metric records into `--metrics` (both accept JSON file paths), then call:

   ```bash
   $CDRI --project <current-project> experiment record --name "<unique-run-name>" --config run-card.json --metrics run-metrics.json --outcome mixed --interpretation "<conditional lesson; interpretation, not observation>" --artifact <original-result-file>
   ```

   Select `positive|negative|null|mixed` from evidence; `mixed` is not a substitute for unknown. For
   `negative|null`, pass `--negative negative-analysis.json` answering `module_ineffective`,
   `problem_misformulated`, `supervision_cannot_identify`, `data_quality_limits`, `baseline_captures_signal`,
   `new_mechanistic_insight` (use `unknown` as needed). If no outcome can be established, use `kg node <id>
   LocalExperiment "<run label>" --props run-card.json --source-type local_experiment --artifact <original-file>`
   to store the observed run with an unknown outcome. No artifact means `user_reported` or `unverified`;
   generated summaries cannot replace missing original experiment evidence.
3. `experiment record --interpretation` creates a project-local ScientificClaim at `agent_inference` linked
   via `SUPPORTS`. Read `kg show <returned-experiment-id>` to get that existing claim ID, then enrich **that
   existing node** with `kg node <existing-claim-id> ScientificClaim "<lesson label>" --props lessons.json
   --status agent_inference --source-type agent --ref <experiment-id>`. This preserves project scope and
   stores full lessons beyond the short claim label. For unknown-outcome runs, retain lessons in the
   LocalExperiment props with explicit per-lesson statuses instead of creating a global claim.
4. `lessons.json` should contain observations/source locations, strengths, weaknesses, conditional lessons,
   applicability, confounders, counterevidence, confidence rationale, and proposed next tests. Each conclusion
   names its source experiment IDs and code locations, with its own status. Include a top-level `rationale`
   string summarizing the task, mechanism and key lessons: the current semantic index reads that field but
   not arbitrary lesson properties (keyword search indexes all properties). Use `kg link` with `SUPPORTS`,
   `CONTRADICTS` or `INSPIRES_HYPOTHESIS` when the endpoints and relation are established. Interpretive links
   use `--status agent_inference --source-type agent`; proposals remain `hypothesis`.
5. Reuse with `kg search "<task or mechanism>" --mode semantic` and inspect `kg show` for the evidence, scope,
   artifact version and limitations. Apply lessons to the current question only after checking conditions;
   prior local success is not proof of cross-domain transfer. Raw runs and lessons stay project-local.

## Report and handoff

Report in Chinese with the skill's evidence labels: choice and source scope; reviewed vs omitted runs;
metrics and protocol gaps; run-specific code confidence; per-model strengths/weaknesses; conditional lessons
with counterevidence; and the smallest useful next experiments. Name the KB records actually created or reused.
If nothing usable was found, explain the missing evidence and continue the original mode without inventing lessons.

Feed supported strengths and open failures into diagnosis, relevant mechanisms into transfer/literature queries,
and untested improvements into ideation as hypotheses. History informs the selected workflow; it does not
replace independent literature evidence or change frozen project decisions.

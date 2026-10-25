# Literature-guided diagnosis

## When to trigger

Trigger on non-trivial research problems: plateau, below a simple baseline, poor OOD/unseen generalization,
prediction collapse, train-test gap, reproduction failure, abnormal loss, complexity bottleneck, results that
contradict theory or the user's expectation. Do **not** run a literature search for routine software errors
(syntax, import, path, shape mismatch, OOM, wrong kwargs) - `diagnose triage` detects these and says so.

## Order

1. Collect facts: `diagnose log train.csv --metric-col val_metric --baseline X [--lower-better]`,
   `diagnose preds preds.csv --group-col <entity>`, `audit leakage`, `audit metric`.
2. `diagnose triage "<symptom>" --obs log.json --obs preds.json --topic "<task>" --mechanism <id>
   --component "<module>"` → ordered problem types:
   implementation_bug → data_processing_error → evaluation_mismatch → optimization_failure →
   representation_failure → inductive_bias_mismatch → label_noise → dataset_shift → identifiability_limit.
3. Local checks first. The literature gate opens only when the problem is reproducible (`--reproducible` or
   `--attempts ≥ 2`) **and** the local types are checked (`--done implementation_bug --done
   data_processing_error`). Then use `targeted_queries` with `search` or a small landscape plan.
4. `--open` creates a worksheet; record each check: `diagnose check <id> "<check>" "<outcome>" --artifact f`.
5. Conclude: `diagnose conclude <id> --hypothesis ... --type <problem type> --verdict supported|refuted|inconclusive
   --mechanism ... --for ... --against ... --paper <doi> --uncertainty ... --artifact f`. Literature mechanisms
   are linked as EXPLAINS_FAILURE (agent_inference - analogy, not proof).
6. For each fix proposal give: problem type, evidence for/against, mechanistic explanation, relevant papers,
   minimal discriminating experiment, expected outcome, risk, and whether it requires changing a frozen decision.

## Rules

- Do not add model complexity as the default fix. Do not change the research direction after one bad run.
- Never modify baselines, weights or launch large training without authorization; respect `project freeze`.
- Negative and null results must be recorded: `experiment record --outcome negative|null --negative '{...}'`
  requires answers (or "unknown") for: module_ineffective, problem_misformulated, supervision_cannot_identify,
  data_quality_limits, baseline_captures_signal, new_mechanistic_insight.
- Experiments without an existing artifact file are stored as user_reported, not experiment_observed.

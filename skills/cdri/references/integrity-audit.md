# Data and evaluation integrity

## Provenance

`audit provenance [--profile bio]` prints a checklist template (raw source/version, technology, sample unit,
cleaning, filtering, normalization and fit scope, features, labels, augmentation, batch correction and fit scope,
split strategy/unit, leakage checks, experiment differences, code-vs-paper consistency; bio adds hierarchy levels,
replicates, gene namespace, genome build, annotations, platform, species, conditions, controls, spatial leakage,
label noise, assay bias). Fill it with evidence and run `audit provenance --check filled.json`: "verified"
without evidence is flagged. A dataset name alone never establishes comparability.

## Leakage

`audit leakage data.csv --split split --group donor --group batch --feature seq --coord x --coord y
--coord-group slide --radius 50`:
- group overlap across splits for each hierarchy level the claim refers to (unseen donor ⇒ group by donor);
- identical feature rows across splits;
- spatial proximity of evaluation points to training points within the same slide;
- hierarchy-like columns that were not checked are listed.

## Metrics

`ontology metrics` / `audit metric-info "<name>"` give definitions, direction, required specification and pitfalls.
`audit metric preds.csv --metric spearman --true y --pred yhat --group gene --group perturbation` recomputes the
metric pooled and per group (mean/median over groups) and warns when aggregation changes the value.

## Comparability

`audit compare --results results.json` with
`{"results": [{"id", "source", "model", "metric", "value", "protocol": {split, split_unit, aggregation,
unit_of_analysis, preprocessing, ...}}]}` → pairwise verdict `comparable | not_directly_comparable |
unknown_comparability` with the differing fields; rankings only within fully comparable groups. Report
everything else as **Not Directly Comparable**. `audit checklist` gives fair-benchmark items (same split,
supervision, test-time information, pretraining disclosure, overlap checks, compute, tuned baselines,
preprocessing, no test-set selection, seed variance).

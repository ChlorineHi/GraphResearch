"""Data integrity: group / duplicate / spatial leakage across splits; provenance checklists;
benchmark comparability matrices (Not Directly Comparable instead of fake leaderboards)."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Sequence

from .. import config
from ..diagnose.logs import read_table
from .metrics import lookup

BIO_LEVELS = ["species", "donor", "patient", "individual", "batch", "sample", "slide", "tissue", "cell", "replicate",
              "plate", "assay", "platform", "condition", "perturbation", "tf", "protein", "gene", "family",
              "cluster", "chromosome"]


def split_leakage(path: str, split_col: str, group_cols: Sequence[str] = (), feature_cols: Sequence[str] = (),
                  coord_cols: Sequence[str] = (), coord_group: Optional[str] = None, radius: float = 0.0,
                  train_label: str = "train") -> dict:
    rows = read_table(path)
    cols = sorted({k for r in rows for k in r})
    findings: List[dict] = []
    splits: Dict[str, List[dict]] = {}
    for r in rows:
        splits.setdefault(str(r.get(split_col)), []).append(r)
    for g in group_cols:
        member: Dict[str, set] = {}
        for s, rs in splits.items():
            for r in rs:
                member.setdefault(str(r.get(g)), set()).add(s)
        shared = {k: sorted(v) for k, v in member.items() if len(v) > 1}
        findings.append({"check": f"group overlap on '{g}'", "n_groups": len(member), "n_shared": len(shared),
                         "examples": dict(list(shared.items())[:5]),
                         "severity": "high" if shared else "none",
                         "meaning": f"{len(shared)} '{g}' values appear in more than one split" if shared else
                                    f"each '{g}' is confined to one split"})
    if feature_cols:
        seen: Dict[str, str] = {}
        dups = 0
        examples = []
        for s, rs in splits.items():
            for r in rs:
                h = hashlib.sha1("|".join(str(r.get(c)) for c in feature_cols).encode()).hexdigest()
                if h in seen and seen[h] != s:
                    dups += 1
                    if len(examples) < 5:
                        examples.append({"splits": [seen[h], s], "features": {c: r.get(c) for c in feature_cols}})
                seen.setdefault(h, s)
        findings.append({"check": "identical feature rows across splits", "n_cross_split_duplicates": dups,
                         "examples": examples, "severity": "high" if dups else "none"})
    if coord_cols and radius > 0 and len(coord_cols) == 2:
        x, y = coord_cols
        train = [r for r in splits.get(train_label, [])]
        grid: Dict[tuple, List[tuple]] = {}
        for r in train:
            try:
                px, py = float(r[x]), float(r[y])
            except (KeyError, ValueError, TypeError):
                continue
            grid.setdefault((str(r.get(coord_group)) if coord_group else "", int(px // radius), int(py // radius)),
                            []).append((px, py))
        near = total = 0
        for s, rs in splits.items():
            if s == train_label:
                continue
            for r in rs:
                try:
                    px, py = float(r[x]), float(r[y])
                except (KeyError, ValueError, TypeError):
                    continue
                total += 1
                gk = str(r.get(coord_group)) if coord_group else ""
                cx, cy = int(px // radius), int(py // radius)
                hit = any(math.hypot(px - a, py - b) <= radius
                          for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                          for a, b in grid.get((gk, cx + dx, cy + dy), []))
                near += hit
        frac = near / total if total else 0.0
        findings.append({"check": f"spatial proximity (≤{radius}) of non-train points to train points"
                                  + (f" within same '{coord_group}'" if coord_group else ""),
                         "fraction_near_train": round(frac, 4), "n_eval_points": total,
                         "severity": "high" if frac > 0.5 else "medium" if frac > 0.1 else "low",
                         "meaning": "spatial autocorrelation can leak labels; consider block/slide-level splits"})
    hier = [c for c in cols if any(l in c.lower() for l in BIO_LEVELS)]
    unchecked = [c for c in hier if c not in group_cols and c != split_col]
    return {"file": path, "n_rows": len(rows), "splits": {k: len(v) for k, v in splits.items()},
            "findings": findings,
            "hierarchy_columns_not_checked": unchecked,
            "advice": ("Re-run with --group for each hierarchy level the generalization claim refers to "
                       "(e.g. unseen donor => group by donor).") if unchecked else ""}


def provenance_checklist(profile: str = "generic") -> dict:
    generic = ["raw_source_and_version", "acquisition_technology", "unit_of_sample", "cleaning_steps",
               "filtering_criteria", "normalization_and_fit_scope", "feature_extraction", "label_construction",
               "augmentation", "batch_correction_and_fit_scope", "split_strategy_and_unit",
               "leakage_checks_performed", "differences_between_experiments", "code_vs_paper_consistency"]
    bio = ["hierarchy_levels(donor/patient/batch/cell/tissue/slide)", "biological_vs_technical_replicates",
           "gene_set_and_identifier_namespace", "genome_build", "cell_type_annotation_source", "platform_differences",
           "species", "experimental_conditions", "control_and_treatment_definition", "spatial_leakage_control",
           "label_noise_estimate", "assay_specific_bias"]
    items = generic + (bio if profile in ("bio", "bioinformatics") else [])
    return {"profile": profile, "template": {k: {"value": "", "evidence": "", "status": "unknown"} for k in items},
            "instructions": "status in verified | reported | unknown | not_applicable; evidence = file/line, paper "
                            "section or command output. Dataset names alone do not establish comparability."}


def check_provenance(filled: Dict[str, Any]) -> dict:
    unknown, unsupported = [], []
    for k, v in filled.items():
        if not isinstance(v, dict):
            continue
        if v.get("status", "unknown") == "unknown":
            unknown.append(k)
        elif v.get("status") == "verified" and not v.get("evidence"):
            unsupported.append(k)
    return {"n_items": len(filled), "unknown": unknown, "verified_without_evidence": unsupported,
            "complete": not unknown and not unsupported}


def comparability(results: List[Dict[str, Any]]) -> dict:
    """results: [{"id", "source", "model", "metric", "value", "protocol": {...}}]"""
    fields = config.load_asset("metric_ontology.json")["comparability_fields"]
    norm = []
    for r in results:
        m = lookup(r.get("metric", ""))
        norm.append(dict(r, metric_id=m["id"] if m else r.get("metric"), direction=(m or {}).get("direction"),
                         must_specify=(m or {}).get("must_specify", [])))
    pairs = []
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            a, b = norm[i], norm[j]
            reasons, unknown = [], []
            if a["metric_id"] != b["metric_id"]:
                reasons.append(f"different metrics ({a['metric_id']} vs {b['metric_id']})")
            pa, pb = a.get("protocol") or {}, b.get("protocol") or {}
            for f in fields + sorted(set(a["must_specify"]) | set(b["must_specify"])):
                va, vb = pa.get(f), pb.get(f)
                if va is None or vb is None:
                    unknown.append(f)
                elif str(va).lower() != str(vb).lower():
                    reasons.append(f"{f}: {va!r} vs {vb!r}")
            verdict = "not_directly_comparable" if reasons else ("unknown_comparability" if unknown else "comparable")
            pairs.append({"a": a.get("id"), "b": b.get("id"), "verdict": verdict, "differences": reasons,
                          "unspecified": sorted(set(unknown))})
    groups: List[List[str]] = []
    for r in norm:
        placed = False
        for g in groups:
            if all(next(p for p in pairs if {p["a"], p["b"]} == {r.get("id"), o})["verdict"] == "comparable"
                   for o in g):
                g.append(r.get("id"))
                placed = True
                break
        if not placed:
            groups.append([r.get("id")])
    rankings = []
    for g in groups:
        if len(g) > 1:
            items = [r for r in norm if r.get("id") in g]
            rev = items[0]["direction"] != "lower"
            rankings.append(sorted(((r["id"], r["value"]) for r in items), key=lambda t: t[1], reverse=rev))
    return {"pairs": pairs, "comparable_groups": groups, "rankings_within_comparable_groups": rankings,
            "rule": "Numbers are ranked only inside groups whose protocols match on every comparability field. "
                    "Everything else is 'Not Directly Comparable' - no cross-group leaderboard is produced."}


def fair_benchmark_checklist() -> List[str]:
    return ["same data split (and split unit)", "same supervision signal", "same information available at test time",
            "pretraining resources disclosed", "possible train/pretrain-test overlap checked", "parameter count and "
            "compute reported", "baselines tuned with comparable budget", "identical preprocessing",
            "no test-set-driven model selection", "variance over seeds / confidence intervals"]

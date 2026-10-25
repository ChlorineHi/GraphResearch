"""Metric implementations (pure Python, tie-aware) and recomputation at different aggregation levels, to show
how 'the same metric' changes with the unit of analysis."""

from __future__ import annotations

import math
import re
import statistics
from typing import Callable, Dict, List, Optional, Sequence

from .. import config
from ..diagnose.logs import read_table


def _rank(xs: Sequence[float]) -> List[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(y: Sequence[float], p: Sequence[float]) -> float:
    n = len(y)
    if n < 2:
        return float("nan")
    my, mp = sum(y) / n, sum(p) / n
    sy = math.sqrt(sum((a - my) ** 2 for a in y))
    sp = math.sqrt(sum((b - mp) ** 2 for b in p))
    if sy == 0 or sp == 0:
        return float("nan")
    return sum((a - my) * (b - mp) for a, b in zip(y, p)) / (sy * sp)


def spearman(y: Sequence[float], p: Sequence[float]) -> float:
    return pearson(_rank(y), _rank(p))


def mse(y, p):
    return sum((a - b) ** 2 for a, b in zip(y, p)) / len(y)


def mae(y, p):
    return sum(abs(a - b) for a, b in zip(y, p)) / len(y)


def rmse(y, p):
    return math.sqrt(mse(y, p))


def r2(y, p):
    my = sum(y) / len(y)
    tot = sum((a - my) ** 2 for a in y)
    return 1 - sum((a - b) ** 2 for a, b in zip(y, p)) / tot if tot else float("nan")


def auroc(y, s):
    pos = [b for a, b in zip(y, s) if a >= 0.5]
    neg = [b for a, b in zip(y, s) if a < 0.5]
    if not pos or not neg:
        return float("nan")
    ranks = _rank(list(s))
    rp = sum(r for r, a in zip(ranks, y) if a >= 0.5)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def auprc(y, s):
    """Average precision (step-wise, as sklearn.average_precision_score)."""
    pairs = sorted(zip(s, y), key=lambda t: -t[0])
    npos = sum(1 for _, a in pairs if a >= 0.5)
    if not npos:
        return float("nan")
    tp = fp = 0
    ap = 0.0
    i = 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        dtp = sum(1 for k in range(i, j) if pairs[k][1] >= 0.5)
        tp += dtp
        fp += (j - i) - dtp
        if dtp:
            ap += (dtp / npos) * (tp / (tp + fp))
        i = j
    return ap


METRICS: Dict[str, Callable] = {"pearson": pearson, "spearman": spearman, "mse": mse, "mae": mae, "rmse": rmse,
                                "r2": r2, "auroc": auroc, "auprc": auprc}


def ontology() -> dict:
    return config.load_asset("metric_ontology.json")


def _norm_metric(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'s", "").replace("’s", "")).strip()


def lookup(name: str) -> Optional[dict]:
    n = _norm_metric(name)
    metrics = ontology()["metrics"]
    for m in metrics:
        if n in {_norm_metric(x) for x in [m["id"], m["label"], *m["aliases"]]}:
            return m
    toks = set(n.split())
    for m in metrics:
        if m["id"] in toks:
            return m
    return None


def _clean(v: float) -> Optional[float]:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, 6)


def recompute(path: str, metric: str, true_col: str, pred_col: str, group_cols: Sequence[str] = ()) -> dict:
    """Compute the metric pooled and per-group (mean / median over groups) for each grouping column."""
    fn = METRICS[metric]
    rows = read_table(path)
    data = []
    for r in rows:
        try:
            data.append((float(r[true_col]), float(r[pred_col]), r))
        except (KeyError, TypeError, ValueError):
            continue
    y = [a for a, _, _ in data]
    p = [b for _, b, _ in data]
    out = {"metric": metric, "n": len(data), "definition": (lookup(metric) or {}).get("definition"),
           "pooled": _clean(fn(y, p)), "by_group": {}}
    for g in group_cols:
        groups: Dict[str, List[tuple]] = {}
        for a, b, r in data:
            groups.setdefault(str(r.get(g)), []).append((a, b))
        vals = []
        for items in groups.values():
            if len(items) >= 3:
                v = fn([a for a, _ in items], [b for _, b in items])
                if not (isinstance(v, float) and math.isnan(v)):
                    vals.append(v)
        out["by_group"][g] = {"n_groups": len(groups), "n_valid": len(vals),
                              "mean_over_groups": _clean(statistics.mean(vals)) if vals else None,
                              "median_over_groups": _clean(statistics.median(vals)) if vals else None}
    spread = [out["pooled"]] + [v[k] for v in out["by_group"].values() for k in ("mean_over_groups",
                                                                                   "median_over_groups") if v[k] is not None]
    spread = [s for s in spread if s is not None]
    if len(spread) > 1:
        out["range_across_aggregations"] = round(max(spread) - min(spread), 6)
        out["warning"] = ("The same metric name yields different values depending on aggregation; report the "
                          "aggregation explicitly and only compare numbers computed the same way.")
    return out

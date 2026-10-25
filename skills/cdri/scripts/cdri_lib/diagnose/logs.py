"""Training-log and prediction-file analysis (pure Python): NaN/divergence, plateau, generalization gap,
below-baseline, prediction collapse. Reports observations, not causes."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional


def read_table(path: str) -> List[Dict[str, str]]:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix in (".jsonl", ".ndjson") or text.lstrip().startswith("{"):
        return [json.loads(l) for l in text.splitlines() if l.strip()]
    if p.suffix == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("records", [])
    delim = "\t" if p.suffix in (".tsv", ".tab") else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delim))


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def series(rows: List[dict], col: str) -> List[float]:
    return [x for x in (_num(r.get(col)) for r in rows) if x is not None]


def plateau(xs: List[float], window: int = 5, rel_tol: float = 0.01, higher_better: bool = False) -> Optional[dict]:
    if len(xs) < 2 * window:
        return None
    best_before = (max if higher_better else min)(xs[:-window])
    best_recent = (max if higher_better else min)(xs[-window:])
    gain = (best_recent - best_before) if higher_better else (best_before - best_recent)
    scale = abs(best_before) or 1.0
    return {"plateau": gain / scale < rel_tol, "relative_gain_last_window": round(gain / scale, 4), "window": window}


def analyze_log(path: str, train_col: str = "train_loss", val_col: str = "val_loss",
                metric_col: Optional[str] = None, higher_better: bool = True,
                baseline: Optional[float] = None) -> dict:
    rows = read_table(path)
    obs: List[dict] = []
    cols = sorted({k for r in rows for k in r})
    tr, va = series(rows, train_col), series(rows, val_col)
    for name, xs in ((train_col, tr), (val_col, va)):
        bad = [i for i, x in enumerate(xs) if math.isnan(x) or math.isinf(x)]
        if bad:
            obs.append({"symptom": "loss_anomaly", "detail": f"{name} NaN/Inf at steps {bad[:5]}"})
        if len(xs) > 3 and xs[-1] > 10 * (min(xs) + 1e-12) and xs[-1] > xs[0]:
            obs.append({"symptom": "loss_anomaly", "detail": f"{name} diverging: last={xs[-1]:.4g}, min={min(xs):.4g}"})
    if tr:
        pl = plateau(tr)
        if pl and pl["plateau"]:
            obs.append({"symptom": "plateau", "detail": f"{train_col} plateau: {pl}"})
    if tr and va and len(tr) == len(va) and len(tr) >= 6:
        k = max(3, len(tr) // 3)
        tr_trend = tr[-1] - tr[-k]
        va_trend = va[-1] - va[-k]
        best_va = min(range(len(va)), key=lambda i: va[i])
        if tr_trend < 0 and va_trend > 0:
            obs.append({"symptom": "train_test_gap",
                        "detail": f"train loss decreasing ({tr_trend:+.4g}) while val loss increasing ({va_trend:+.4g}) "
                                  f"over last {k} steps; best val at step {best_va}"})
        gap = va[-1] - tr[-1]
        obs.append({"symptom": "info", "detail": f"final val-train loss gap {gap:.4g}"})
    if metric_col:
        ms = series(rows, metric_col)
        if ms:
            pl = plateau(ms, higher_better=higher_better)
            if pl and pl["plateau"]:
                obs.append({"symptom": "plateau", "detail": f"{metric_col} plateau: {pl}"})
            best = max(ms) if higher_better else min(ms)
            if baseline is not None and ((best < baseline) if higher_better else (best > baseline)):
                obs.append({"symptom": "below_simple_baseline",
                            "detail": f"best {metric_col}={best:.4g} vs baseline {baseline:.4g}"})
    return {"file": path, "rows": len(rows), "columns": cols, "observations": obs,
            "note": "observations only; map them to candidate problem types with `cdri diagnose triage`"}


def analyze_predictions(path: str, pred_col: str = "pred", true_col: str = "true",
                        group_col: Optional[str] = None) -> dict:
    rows = read_table(path)
    p, t = [], []
    groups: Dict[str, List[float]] = {}
    for r in rows:
        a, b = _num(r.get(pred_col)), _num(r.get(true_col))
        if a is None or b is None:
            continue
        p.append(a)
        t.append(b)
        if group_col:
            groups.setdefault(str(r.get(group_col)), []).append(a)
    obs = []
    if len(p) < 3:
        return {"file": path, "observations": [{"symptom": "info", "detail": "too few numeric rows"}]}
    sp, st = statistics.pstdev(p), statistics.pstdev(t)
    ratio = sp / st if st else float("nan")
    if st and ratio < 0.1:
        obs.append({"symptom": "prediction_collapse",
                    "detail": f"prediction std / target std = {ratio:.3f} (< 0.1): near-constant predictions"})
    uniq = len({round(x, 6) for x in p})
    if uniq <= max(2, len(p) // 100):
        obs.append({"symptom": "prediction_collapse", "detail": f"only {uniq} distinct predicted values"})
    if groups:
        within = [statistics.pstdev(v) for v in groups.values() if len(v) > 1]
        between = statistics.pstdev([statistics.mean(v) for v in groups.values()]) if len(groups) > 1 else 0.0
        mw = statistics.mean(within) if within else 0.0
        if between > 0 and mw < 0.1 * between:
            obs.append({"symptom": "prediction_collapse",
                        "detail": f"within-{group_col} prediction spread ({mw:.3g}) << between-group spread "
                                  f"({between:.3g}): model may predict a per-group constant"})
    return {"file": path, "n": len(p), "pred_std": round(sp, 6), "true_std": round(st, 6),
            "std_ratio": round(ratio, 4) if st else None, "observations": obs}

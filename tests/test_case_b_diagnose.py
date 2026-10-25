"""Case B: "某个新模型训练正常，但在未见过的测试对象上泛化很差，甚至低于简单基线。"
Synthetic logs/predictions/splits (generated here). Verifies the trivial-error gate, local-checks-first ordering,
the literature gate, targeted queries, leakage detection, worksheet conclusions (with artifacts), frozen
decisions, and mandatory negative-result analysis."""

from __future__ import annotations

import json

from conftest import ok, run, write_json

REQUEST = "某个新模型训练正常，但在未见过的测试对象上泛化很差，甚至低于简单基线。"


def _data(tmp):
    log = ["epoch,train_loss,val_loss,val_spearman"]
    for e in range(40):
        log.append(f"{e},{0.9 * 0.93 ** e + 0.05:.5f},{0.62 + max(0, 10 - e) * 0.03:.5f},{min(0.29, 0.03 * e):.4f}")
    (tmp / "train_log.csv").write_text("\n".join(log), encoding="utf-8")
    preds = ["tf,true,pred"]
    for t in range(6):
        for i in range(10):
            preds.append(f"TF{t},{(i * 7 + t * 3) % 10 / 10:.2f},{0.5 + 0.001 * t:.4f}")
    (tmp / "preds.csv").write_text("\n".join(preds), encoding="utf-8")
    split = ["tf,tf_family,split"]
    fams = ["bHLH", "C2H2", "Homeobox", "bZIP"]
    for i in range(16):
        split.append(f"TF{i},{fams[i % 4]},{'test' if i % 4 == 0 or i == 5 else 'train'}")
    (tmp / "split.csv").write_text("\n".join(split), encoding="utf-8")


def test_case_b_diagnosis_flow(env):
    _data(env.tmp)
    assert ok("route", REQUEST)["mode"] == "diagnose"

    # routine software error: no literature search
    t0 = ok("diagnose", "triage", "ModuleNotFoundError: No module named 'torch_scatter'")
    assert t0["trivial"] and t0["literature_search"] == "not_recommended"

    lg = ok("diagnose", "log", env.tmp / "train_log.csv", "--metric-col", "val_spearman", "--baseline", "0.35")
    syms = {o["symptom"] for o in lg["observations"]}
    assert "below_simple_baseline" in syms and "plateau" in syms
    pr = ok("diagnose", "preds", env.tmp / "preds.csv", "--group-col", "tf")
    assert any(o["symptom"] == "prediction_collapse" for o in pr["observations"])
    obs_p = write_json(env.tmp / "obs.json", {"observations": lg["observations"] + pr["observations"]})

    ok("project", "init", "--name", "tfbind-unseen", "--goal", "generalize to unseen TFs")
    ok("project", "freeze", "keep the PLM-FiLM backbone", "--reason", "agreed with PI; compare objectives only")

    sym = "model trains normally but generalizes poorly to unseen TFs, below simple baseline"
    t1 = ok("diagnose", "triage", sym, "--obs", obs_p, "--topic", "TF binding prediction")
    assert not t1["trivial"] and t1["literature_search"] == "deferred"
    orders = [c["order"] for c in t1["candidate_problem_types"]]
    assert orders == sorted(orders)
    assert t1["candidate_problem_types"][0]["id"] == "implementation_bug"
    assert t1["frozen_decisions"][0]["decision"] == "keep the PLM-FiLM backbone"
    local = [c["id"] for c in t1["candidate_problem_types"] if not c["needs_literature"]]

    args = ["diagnose", "triage", sym, "--obs", obs_p, "--topic", "TF binding prediction", "--attempts", "3",
            "--mechanism", "meta-learning-conditioning", "--component", "FiLM conditioning", "--open"]
    for c in local:
        args += ["--done", c]
    t2 = ok(*args)
    assert t2["literature_search"] == "recommended"
    assert t2["targeted_queries"] and all(q["query"] for q in t2["targeted_queries"])
    wid = t2["worksheet"]

    leak = ok("audit", "leakage", env.tmp / "split.csv", "--split", "split", "--group", "tf_family")
    assert leak["findings"][0]["severity"] == "high"
    (env.tmp / "leakage.json").write_text(json.dumps(leak), encoding="utf-8")
    ok("diagnose", "check", wid, "homology-aware split audit", "4/4 families shared between train and test",
       "--artifact", env.tmp / "leakage.json")

    code, err = run("diagnose", "conclude", wid, "--hypothesis", "x", "--type", "evaluation_mismatch",
                    "--verdict", "supported")
    assert code == 2 and "supporting fact" in err["error"]

    c = ok("diagnose", "conclude", wid,
           "--hypothesis", "validation split shares TF families with training; unseen-TF ability was never measured",
           "--type", "evaluation_mismatch", "--verdict", "supported",
           "--mechanism", "family-level homology lets the model interpolate instead of generalize",
           "--for", "all families occur in both splits (leakage.json)",
           "--against", "collapse also seen within families; may be a second issue",
           "--paper", "doi:10.5555/cdri.fx.004", "--uncertainty", "single dataset",
           "--artifact", env.tmp / "leakage.json")
    fm = c["conclusion"]["failure_node"]
    assert c["conclusion"]["node_status"] == "experiment_observed"   # artifact exists
    node = ok("kg", "show", fm)
    assert node["node"]["scope"] == "project"
    assert any(e["type"] == "EXPLAINS_FAILURE" and e["status"] == "agent_inference" for e in node["in"])

    code, err = run("experiment", "record", "--name", "family-split retrain", "--outcome", "negative",
                    "--metrics", '{"median_spearman": 0.21}')
    assert code == 2 and "negative-result analysis" in err["error"]
    neg = {"module_ineffective": "unknown", "problem_misformulated": "partly: descriptor out of support",
           "supervision_cannot_identify": "ranking loss cannot calibrate across TFs",
           "data_quality_limits": "replicate ceiling 0.47", "baseline_captures_signal": "nearest neighbour ~0.33",
           "new_mechanistic_insight": "generalization limited to descriptor support"}
    e = ok("experiment", "record", "--name", "family-split retrain", "--outcome", "negative",
           "--metrics", '{"median_spearman": 0.21}', "--negative", json.dumps(neg),
           "--interpretation", "unseen-family generalization is not achieved", "--tests", fm)
    assert e["status"] == "user_reported"          # no artifact file -> not experiment_observed
    ws = ok("diagnose", "show", wid)
    assert ws["status"] == "diagnosed" and ws["checks"][0]["artifact_exists"]

#!/usr/bin/env python3
"""Generate docs/04-usage-demo.md by running real CLI commands against the synthetic offline fixtures.

Every output block in the generated document is the actual output of the command shown (truncated for length).
Nothing is hand-written except the step headings."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "cdri" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import fixture_builder  # noqa: E402
from conftest import git_repo_copy, write_json  # noqa: E402
from test_case_a_landscape import _card  # noqa: E402
from test_case_b_diagnose import _data  # noqa: E402
from test_case_c_transfer import PROBLEM, SIGS  # noqa: E402

from cdri_lib import cli  # noqa: E402

OUT: list = []
MAX_LINES = 28


def run(title: str, *args, show=True, max_lines=MAX_LINES, pick=None):
    argv = [str(a) for a in args]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    text = buf.getvalue()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = text
    if show:
        disp = obj
        if pick and isinstance(obj, dict):
            disp = {k: obj[k] for k in pick if k in obj}
        body = disp if isinstance(disp, str) else json.dumps(disp, ensure_ascii=False, indent=2)
        lines = body.splitlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines] + [f"... ({len(body.splitlines()) - max_lines} more lines)"]
        shown = " ".join(a if " " not in a else f'"{a}"' for a in [_short(a) for a in argv])
        OUT.extend([f"### {title}", "", "```text", f"$CDRI {shown}", f"# exit code {code}", *lines, "```", ""])
    return obj


def _short(a: str) -> str:
    return a.replace(str(TMP), "$TMP").replace("\\", "/") if TMP else a


TMP = None


def main() -> int:
    global TMP
    with tempfile.TemporaryDirectory() as td:
        TMP = Path(td)
        home, proj = TMP / "home", TMP / "proj"
        proj.mkdir()
        fx = fixture_builder.build(TMP / "http")
        for k in ("S2_API_KEY", "NCBI_API_KEY", "GITHUB_TOKEN", "CDRI_OFFLINE", "CDRI_EMBEDDINGS"):
            os.environ.pop(k, None)
        os.environ.update(CDRI_HOME=str(home), CDRI_PROJECT=str(proj), CDRI_FIXTURES=str(fx),
                          CDRI_TODAY="2026-06-15")

        OUT.extend(["# CDRI 使用演示（离线合成数据实跑）", "",
                    "> 本文件由 `python tools/run_demo.py` 自动生成：每个代码块都是所示命令的**真实输出**（过长处截断）。",
                    "> 数据来自 `tests/fixture_builder.py` 的**合成 fixture**（标题带 `[SYNTHETIC FIXTURE]`，DOI 前缀 "
                    "`10.5555/cdri.fx.*`），不是真实文献；HTTP 由 `CDRI_FIXTURES` 路由，日期固定为 2026-06-15。",
                    "> `$CDRI` = `python <skill>/scripts/cdri.py`。在 Agent 中，这些命令由 Agent 依据 SKILL.md 调用，"
                    "报告中的 `<!-- AGENT: ... -->` 段落由 Agent 在读过全文后填写。", "",
                    "## Case A：landscape + paper（TF–DNA binding, unseen TF generalization）", ""])
        req = "调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。"
        run("1. 路由：自然语言 → 模式", "route", req)
        run("2. 初始化项目", "project", "init", "--name", "tfbind-unseen", "--goal", "unseen-TF generalization")
        plan_p = TMP / "plan.json"
        run("3. 四通道检索计划（时间窗由当前日期动态推导）", "landscape", "plan",
            "TF-DNA binding specificity prediction for unseen transcription factors",
            "--variant", "zero-shot transcription factor binding prediction",
            "--abstraction", "predict interactions between sequences and unseen entities described by descriptors",
            "--structure", "unseen-entity-interaction", "--out", plan_p, max_lines=6)
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        OUT.extend(["计划文件节选（时间窗、学科路由）与全部查询：", "", "```text",
                    json.dumps({"windows": plan["windows"], "disciplines": [d["id"] for d in plan["disciplines"]]},
                               ensure_ascii=False)] +
                   [f"[{q['lane']}] {q['text']}  -> {','.join(q['sources'])}"
                    + (f"  from {q['date_from']}" if q.get("date_from") else "  (no date floor)")
                    + ("  preprints only" if q.get("preprints_only") else "") for q in plan["queries"]] +
                   ["```", ""])
        run("4. 执行检索（S2 返回 429、dblp 无 fixture → 均如实列入 failures）", "landscape", "run", "--plan", plan_p,
            "--run-id", "demoA", pick=["by_db", "failures", "pub_status", "recency", "raw_records", "unique_records"],
            max_lines=45)
        run("5. 筛选建议（不凑数）", "screen", "suggest", "--run", "demoA", "--tier", "focused", max_lines=20)
        run("6. 筛选决定必须给理由（空理由被拒绝）", "screen", "decide", "paper:doi:10.5555/cdri.fx.001", "--run", "demoA",
            "--tier", "deep", "--reason", " ")
        run("6b. 带理由的决定", "screen", "decide", "paper:doi:10.5555/cdri.fx.001", "--run", "demoA", "--tier", "deep",
            "--reason", "directly addresses unseen-TF generalization with a homology-aware split")
        run("7. 引用核验：不存在的 DOI", "paper", "verify", "doi:10.5555/cdri.fx.999")
        fetched = run("8. 全文获取（合法 OA 级联 + read plan + sentinel）", "paper", "fetch", "arxiv:9912.00001", "--plan",
            pick=["paper_id", "tried", "status", "kind", "lines", "sentinel", "read_plan", "section_kinds",
                  "code_links", "warnings"], max_lines=40)
        run("8b. 没有合法 OA 全文时如实报告", "paper", "fetch", "doi:10.5555/cdri.fx.004", pick=["status", "tried", "reason"])
        run("9. 通过 CLI 读 Methods 章节（写入阅读台账）", "paper", "section", "arxiv:9912.00001", "methods", max_lines=22)
        repo, sha = git_repo_copy(TMP / "repo")
        run("10. 代码-方法映射（commit 固定）", "code", "analyze", repo, pick=["repo", "by_role"], max_lines=30)
        card = write_json(TMP / "card.json", _card(sha, repo))
        run("11. Paper Card 写入知识库：未读章节的结论不会成为 author_claim", "paper", "ingest", card,
            pick=["paper_id", "reading_depth", "written", "write_warnings"], max_lines=30)
        run("12. 用 sentinel 确认已读完全文", "paper", "confirm", "arxiv:9912.00001", fetched["sentinel"])
        run("13. 重新写入：不自动升级，进入待审队列", "paper", "ingest", write_json(TMP / "card2.json", _card(sha, repo)),
            pick=["write_warnings"], max_lines=12)
        run("14. 待审升级列表", "kg", "pending", max_lines=18)
        run("15. 显式升级（需要引用已读章节）", "kg", "promote", "result:paper-arxiv-9912-00001-0", "--status",
            "author_claim", "--source-type", "paper_fulltext", "--ref", "paper:arxiv:9912.00001", "--location",
            "3 Results")
        run("16. Deep Method Review 报告（节选）", "report", "paper", "--id", "arxiv:9912.00001", max_lines=45)

        OUT.extend(["## Case B：diagnose（训练正常，但未见对象泛化差、低于基线）", ""])
        _data(TMP)
        run("1. 常规软件错误不触发文献检索", "diagnose", "triage", "ModuleNotFoundError: No module named 'torch_scatter'",
            pick=["trivial", "literature_search", "advice"])
        lg = run("2. 训练日志分析", "diagnose", "log", TMP / "train_log.csv", "--metric-col", "val_spearman",
                 "--baseline", "0.35", max_lines=24)
        pr = run("3. 预测分布分析", "diagnose", "preds", TMP / "preds.csv", "--group-col", "tf", max_lines=16)
        obs = write_json(TMP / "obs.json", {"observations": lg["observations"] + pr["observations"]})
        run("4. 冻结决策", "project", "freeze", "keep the PLM-FiLM backbone", "--reason", "agreed with PI")
        run("5. 分诊：先做本地检查，文献检索延后", "diagnose", "triage",
            "model trains normally but generalizes poorly to unseen TFs, below simple baseline", "--obs", obs,
            "--topic", "TF binding prediction",
            pick=["literature_search", "candidate_problem_types", "frozen_decisions"], max_lines=36)
        run("6. 数据泄漏审计（按 TF family 分组）", "audit", "leakage", TMP / "split.csv", "--split", "split", "--group",
            "tf_family", max_lines=22)
        run("7. 负面结果必须带分析", "experiment", "record", "--name", "family-split retrain", "--outcome", "negative",
            "--metrics", '{"median_spearman": 0.21}')

        OUT.extend(["## Case C：transfer（空间细胞扰动预测，跨学科方法迁移）", "",
                    "另一个项目目录（`--project $TMP/proj2`）；全局知识库与 Case A 共享，项目层相互隔离。", ""])
        p2 = TMP / "proj2"
        p2.mkdir()
        P = ("--project", p2)
        run("1. 路由", "route", "研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。", pick=["mode", "reasons"])
        run("2. 新项目", *P, "project", "init", "--name", "spatial-perturb", "--goal", "spatial perturbation response")
        run("3. 定义问题签名（问题结构，而非关键词）", *P, "project", "problem", write_json(TMP / "problem.json", PROBLEM),
            pick=["problem_id"])
        for m, s in SIGS.items():
            run("", *P, "signature", "add", m, write_json(TMP / f"{m.split(':')[1]}.json", s), "--location",
                "synthetic fixture signature", show=False)
        scan = run("4. 结构匹配扫描", *P, "transfer", "scan", "--min-structural", "0.0", show=False)
        OUT.extend(["### 4. 结构匹配扫描（结构相似度 vs 词面相似度）", "", "```text",
                    "$CDRI --project $TMP/proj2 transfer scan --min-structural 0.0", "# 节选：每个候选的关键字段"] +
                   [json.dumps({k: c.get(k) for k in ("method_id", "source_domain", "structural_similarity",
                                                      "lexical_similarity", "new_mechanisms_for_target", "flags")},
                               ensure_ascii=False) for c in scan["candidates"]] + ["```", ""])
        run("5. 记录项目事实", *P, "project", "fact", "mass-conservation-or-unbalanced-relaxation", "false", "--note",
            "perturbation kills cells", pick=["facts"])
        run("6. 适用性检查与负迁移风险", *P, "transfer", "check", "method:fixture-ot-cell-response", max_lines=40)
        rec = run("7. 记录迁移假设（状态 = hypothesis）", *P, "transfer", "record", "method:fixture-ot-cell-response",
                  "--rationale", "shared unpaired-alignment structure", pick=["transfer_id", "status"])
        run("8. 迁移子图（Mermaid；虚线 = 弱证据）", *P, "graph", "export", "--view", "transfer", "--format", "mermaid",
            max_lines=40)
        run("9. 来源追溯", *P, "graph", "lineage", rec["transfer_id"], max_lines=24)
        run("10. 项目隔离：Case A 项目的冻结决策在此不可见", *P, "project", "show", pick=["name", "frozen_decisions"])

        OUT.extend(["## 会话续接", ""])
        run("开始会话", "session", "start", "landscape", "TF binding unseen generalization")
        run("记录待办", "session", "todo", "read Results of fx.004 critique")
        run("续接摘要", "session", "resume", max_lines=24)

    dest = ROOT / "docs" / "04-usage-demo.md"
    dest.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

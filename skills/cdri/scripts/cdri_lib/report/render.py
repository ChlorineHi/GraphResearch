"""Layered research reports (中文叙述 + English terms). Data-driven sections are rendered from run logs and the KB;
sections that require interpretation are explicitly marked for the agent and never auto-filled with claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .. import config
from .. import project as proj
from ..ids import norm_text, parse_identifier, slug
from ..kg import epistemics as ep
from ..kg import views
from ..kg.store import KnowledgeBase
from ..retrieval import run as R

LEGEND = ("> 证据标签：**Verified Fact**（登记处/代码/本地实验核验）· **Author Claim**（论文原文主张）· "
          "**Agent Interpretation**（Agent 推断）· **Hypothesis**（待检验假设）· **Unsupported / Unverified**。\n")
AGENT = "<!-- AGENT: 需要 Agent 基于已读全文撰写；只能引用知识库中的条目 ID，并标注证据标签 -->"
STATUS_ZH = {"published": "正式发表", "accepted": "已接收", "preprint": "预印本", "unknown": "状态未知"}


def _link(r: dict) -> str:
    if r.get("doi"):
        return f"[doi:{r['doi']}](https://doi.org/{r['doi']})"
    if r.get("arxiv"):
        return f"[arXiv:{r['arxiv']}](https://arxiv.org/abs/{r['arxiv']})"
    if r.get("pmid"):
        return f"[PMID:{r['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/)"
    return r.get("url") or r.get("id", "")


def _paper_line(r: dict, decision: Optional[dict] = None) -> str:
    s = r.get("signals") or {}
    first = (r.get("authors") or ["?"])[0]
    venue = r.get("venue") or "?"
    badge = STATUS_ZH.get(r.get("pub_status", "unknown"), r.get("pub_status"))
    extra = f" · 筛选: **{decision['tier']}**（{decision['reason']}）" if decision else ""
    vers = " · 有预印本版本" if any(v.get("relation") == "preprint_version" for v in r.get("versions") or []) else ""
    return (f"- **{r.get('title')}** — {first} et al., {r.get('year') or 'n.d.'}, *{venue}* "
            f"[{badge}{vers}] · {_link(r)} · relevance={s.get('relevance')} · {s.get('recency')}{extra}")


def landscape(run_id: str, project: Optional[str] = None, max_per_lane: int = 25) -> str:
    d = R.run_dir(project, run_id)
    plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    recs = [r.to_dict() for r in R.load_records(project, run_id)]
    dec = R.decisions(project, run_id)
    L: List[str] = [f"# Research Landscape：{plan['topic']}", "",
                    f"- 运行 ID：`{run_id}` · 研究强度：{plan['intensity']} · 生成日期：{plan['windows']['today']}",
                    f"- 动态时间窗：recent ≥ {plan['windows']['recent_from']}；core ≥ {plan['windows']['core_from']}；"
                    "foundational 无下限", f"- 识别学科：{', '.join(x['id'] for x in plan['disciplines']) or '未识别'}",
                    f"- 候选问题结构：{', '.join(s['id'] + '（' + s['match'] + '）' for s in plan['structures']) or '无'}",
                    "", LEGEND, "## 1. 检索覆盖（由检索日志计算）", "",
                    "| 数据库 | 状态计数 |", "|---|---|"]
    if "status" in summary:
        overall = {"complete": "计划内来源已完成检索", "partial": "部分来源失败，检索已降级继续",
                   "failed": "所有已尝试来源均失败，本轮没有成功检索", "not_run": "没有实际执行检索请求"}
        L[2:2] = [f"- 总体状态：**{overall[summary['status']]}**；响应来源："
                  + (", ".join(summary["available_sources"]) or "无")
                  + f"；已尝试调用 {summary['attempted_calls']} 次，跳过 {summary['skipped_calls']} 次。"]
        if summary.get("source_filter"):
            L[3:3] = ["- 本轮限定来源：" + ", ".join(summary["source_filter"])
                      + "；计划中未查询的来源：" + (", ".join(summary["excluded_sources"]) or "无")
                      + "。完成状态仅针对本轮范围，未查询不等于成功。"]
    for db, st in summary["by_db"].items():
        L.append(f"| {db} | {', '.join(f'{k}={v}' for k, v in st.items())} |")
    L += ["", "| 通道 | 查询数 | 返回结果数 |", "|---|---|---|"]
    for lane, v in summary["by_lane"].items():
        L.append(f"| {lane} | {v['queries']} | {v['results']} |")
    L += ["", f"原始结果 {summary['raw_records']} 条，去重后 {summary['unique_records']} 条。发表状态："
          + "，".join(f"{STATUS_ZH.get(k, k)} {v}" for k, v in summary["pub_status"].items()) + "。"]
    if summary["failures"]:
        L += ["", "**未完成的检索（必须如实报告）**：", ""]
        for f in summary["failures"][:30]:
            L.append(f"- {f['db']} · `{f['query']}` → **{f['status']}**：{(f.get('error') or '')[:160]}")
    for recovery in summary.get("source_recovery", []):
        L.append(f"- 恢复建议（{recovery['db']}）：{recovery['action']}")
    L += ["", "## 2. 按检索通道的文献版图", ""]
    lane_zh = {"in_domain": "A. In-domain（领域内直接相关）", "adjacent": "B. Adjacent-domain（相邻领域）",
               "distant": "C. Distant-domain（远域：数学结构相似）",
               "contradictory": "D. Contradictory / Alternative（反证与替代建模）"}
    for lane, title in lane_zh.items():
        rs = [r for r in recs if lane in (r.get("signals") or {}).get("lanes", [])]
        if not rs:
            continue
        L += [f"### {title}", ""]
        qs = [q for q in plan["queries"] if q["lane"] == lane]
        L.append("检索式：" + "；".join(f"`{q['text']}`（{q['rationale']}）" for q in qs[:6]))
        L.append("")
        for r in rs[:max_per_lane]:
            L.append(_paper_line(r, dec.get(r["id"])))
        L.append("")
    L += ["## 3. 筛选分层", ""]
    for tier in ("focused", "deep", "exclude"):
        ids = [i for i, e in dec.items() if e["tier"] == tier]
        L.append(f"- **{tier}**（{len(ids)}）：" + ("、".join(f"`{i}`" for i in ids) if ids else "尚未决定"))
    L += ["", "## 4. 主要科学问题、研究范式与方法分类", "", AGENT, "",
          "## 5. 最新重要研究 vs 奠基性研究", "", AGENT, "",
          "## 6. 关键争议与开放问题（须引用 D 通道证据）", "", AGENT, "",
          "## 7. 方法局限", "", "必须区分：作者承认的 Limitation / 由实验推断的 Limitation / Agent 提出的潜在 Limitation。", AGENT, ""]
    return "\n".join(L)


def paper(paper_id: str, kb: KnowledgeBase) -> str:
    pid = parse_identifier(paper_id).canonical
    n = kb.get_node(pid)
    if not n:
        raise KeyError(pid)
    p = n["props"]
    head = [f"`{pid}`", STATUS_ZH.get(p.get("pub_status"), "状态未知"), p.get("venue") or "venue 未知",
            str(p.get("year") or "年份未知"), _link(dict(p, id=pid))]
    L = [f"# Deep Method Review：{n['label']}", "", "- ID：" + " · ".join(x for x in head if x),
         f"- 阅读深度：**{p.get('reading_depth', 'metadata')}**（阅读台账：{len(kb.g.ledger(pid))} 个章节记录）"]
    for e in kb.edges(src=pid, etype="VERSION_OF"):
        other = kb.get_node(e["dst"]) or {"props": {}}
        L.append(f"- 版本关系：本条为 `{e['dst']}` 的另一版本（后者：{STATUS_ZH.get(other['props'].get('pub_status'), '状态未知')}"
                 f"，{other['props'].get('venue') or 'venue 未知'}）。所读内容来自本版本；与正式版本的差异未核对。")
    for e in kb.edges(dst=pid, etype="VERSION_OF"):
        L.append(f"- 版本关系：`{e['src']}` 是本条的另一版本（如预印本）；所读内容的版本请以阅读台账为准。")
    L += ["", LEGEND]
    methods = [e["dst"] for e in kb.edges(src=pid, etype="USES_METHOD")]
    for mid in methods:
        m = kb.get_node(mid)
        if not m:
            continue
        L += [f"## 方法：{m['label']}", ""]
        f = m["props"].get("formulation") or {}
        if f:
            L += ["### 输入 / 输出 / 监督 / 目标", ""] + [f"- **{k}**：{v}" for k, v in f.items() if v] + [""]
        eqs = m["props"].get("equations") or []
        if eqs:
            L += ["### 公式（含原文位置）", ""]
            for e in eqs:
                L.append(f"- {e.get('label')}（{e.get('role')}，{e.get('location')}）：$${e.get('latex')}$$")
            L.append("")
        sections = [("USES_MECHANISM", "机制 Mechanism"), ("USES_OPERATOR", "核心算子"),
                    ("HAS_INDUCTIVE_BIAS", "归纳偏置"), ("DEPENDS_ON_ASSUMPTION", "依赖假设"),
                    ("IMPLEMENTED_BY", "代码映射"), ("HAS_LIMITATION", "Limitation")]
        for et, title in sections:
            es = kb.edges(src=mid, etype=et)
            if not es:
                continue
            L += [f"### {title}", ""]
            for e in es:
                t = kb.get_node(e["dst"]) or {"label": e["dst"], "props": {}}
                extra = ""
                if et == "IMPLEMENTED_BY":
                    extra = f" · formula={e['props'].get('formula')} · match={e['props'].get('match')} " \
                            f"{t['props'].get('permalink') or ''}"
                if et == "HAS_LIMITATION":
                    extra = f" · category={e['props'].get('category')}"
                prov = kb.provenance(e["id"])
                loc = "; ".join(dict.fromkeys(f"{x['source_type']}@{x['location']}"
                                              for x in prov if x.get("location")))[:120]
                L.append(f"- {t['label']} — **{ep.label(e['status'])}**{extra}" + (f" · 来源：{loc}" if loc else ""))
            L.append("")
        impl = m["props"].get("implementation") or {}
        if impl:
            L += ["### 实现细节", ""] + [f"- **{k}**：{v}" for k, v in impl.items()] + [""]
    claims = [kb.get_node(e["dst"]) for e in kb.edges(src=pid, etype="MAKES_CLAIM")]
    if claims:
        L += ["## 创新点（Methodological Innovation）", ""]
        for c in claims:
            if c:
                L.append(f"- {c['label']} — **{ep.label(c['status'])}** · kind={c['props'].get('kind')} · "
                         f"与已有工作差别：{c['props'].get('novel_vs_prior')}")
        L.append("")
    results = [kb.get_node(e["dst"]) for e in kb.edges(src=pid, etype="REPORTS_RESULT")]
    if results:
        L += ["## 关键实验证据", ""]
        for r in results:
            if r:
                tag = "（负面结果）" if r["props"].get("negative") else ""
                L.append(f"- {r['label']}{tag} — **{ep.label(r['status'])}** · ablation={r['props'].get('is_ablation')}"
                         f" · OOD={r['props'].get('is_ood')}")
        L.append("")
    for link in kb.edges(src=pid, etype="LINKS_TO"):
        analysis = kb.get_node(link["dst"])
        if not analysis or analysis["retracted"] or analysis["props"].get("claim_type") != "research_story":
            continue
        story = analysis["props"]["research_story"]
        L += ["## 研究故事与科学贡献（Research Story）", "",
              f"- 知识卡：`{analysis['id']}` — **{ep.label(analysis['status'])}**",
              "- 以下为基于已读原文的分析；实际录用原因未知。", ""]
        for field, title in (("summary", "核心叙事"), ("selection_reason", "选择理由"),
                             ("comparison_scope", "比较范围"), ("contribution_types", "贡献类型"),
                             ("beyond_sota", "性能之外的贡献"),
                             ("counterfactual_without_sota", "移除 SOTA 后仍成立什么")):
            if story.get(field):
                value = story[field]
                L.append(f"- **{title}**：{', '.join(map(str, value)) if isinstance(value, list) else value}")
        for step, item in (story.get("arc") or {}).items():
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            sources = item.get("evidence")
            locations = [str(s.get("location") or "?") for s in sources if isinstance(s, dict)] \
                if isinstance(sources, list) else []
            L.append(f"- **{step}**：{item['text']} · 原文：{'; '.join(locations) or '缺失'}")
        for alternative in story.get("alternative_explanations") or []:
            L.append(f"- **替代解释/证据缺口**：{alternative}")
        for lesson in story.get("transferable_lessons") or []:
            if isinstance(lesson, dict):
                L.append(f"- **可复用经验（{ep.label(analysis['status'])}）**：{lesson.get('lesson', '')}"
                         f" · 适用条件：{lesson.get('conditions') or '未知'}"
                         f" · 误用风险：{lesson.get('misuse_risk') or '未知'}")
            else:
                L.append(f"- **可复用经验（{ep.label(analysis['status'])}）**：{lesson}")
        if analysis["props"].get("evidence_gaps"):
            L.append("- **未解决缺口**：" + "; ".join(analysis["props"]["evidence_gaps"]))
        L.append("")
    L += ["## 与其他方法的本质差别", "", AGENT, ""]
    return "\n".join(L)


def synthesis(kb: KnowledgeBase, project: Optional[str] = None) -> str:
    L = ["# Research Synthesis（由知识图谱关系计算）", "", LEGEND]
    by_assump: Dict[str, List[str]] = {}
    for e in kb.edges(etype="DEPENDS_ON_ASSUMPTION"):
        by_assump.setdefault(e["dst"], []).append(e["src"])
    shared = {a: ms for a, ms in by_assump.items() if len(set(ms)) > 1}
    L += ["## 1. 共享基本假设的方法", ""]
    L += [f"- `{a}` ← {', '.join(sorted(set(ms)))}" for a, ms in shared.items()] or ["- （暂无）"]
    by_struct: Dict[str, List[str]] = {}
    for e in kb.edges(etype="INSTANCE_OF_STRUCTURE"):
        by_struct.setdefault(e["dst"], []).append(e["src"])
    L += ["", "## 2. 解决同一抽象问题的研究", ""]
    for s, ms in by_struct.items():
        doms = sorted({x["dst"].split(":", 1)[1] for m in ms for x in kb.edges(src=m, etype="IN_DOMAIN")})
        L.append(f"- `{s}` ← {', '.join(sorted(set(ms)))}（领域：{', '.join(doms) or '?'}）")
    if not by_struct:
        L.append("- （暂无）")
    L += ["", "## 3. 冲突证据（CONTRADICTS，保留而不强行综合）", ""]
    cons = kb.edges(etype="CONTRADICTS")
    L += [f"- {e['src']} ⟂ {e['dst']} — **{ep.label(e['status'])}**" for e in cons] or ["- （暂无记录）"]
    L += ["", "## 4. 揭示相似 Limitation 的研究", ""]
    lims = []
    for e in kb.edges(etype="HAS_LIMITATION"):
        n = kb.get_node(e["dst"])
        if n:
            lims.append((e["src"], n, set(norm_text(n["label"]).split())))
    pairs = []
    for i in range(len(lims)):
        for j in range(i + 1, len(lims)):
            a, b = lims[i], lims[j]
            if a[0] != b[0] and a[2] and b[2]:
                jac = len(a[2] & b[2]) / len(a[2] | b[2])
                if jac >= 0.35:
                    pairs.append(f"- {a[0]}「{a[1]['label'][:60]}」≈ {b[0]}「{b[1]['label'][:60]}」（词汇重叠 {jac:.2f}，需人工确认）")
    L += pairs or ["- （暂无）"]
    L += ["", "## 5. 跨领域机制联系与迁移假设", ""]
    nodes = {n["id"]: n for n in kb.nodes("Method")}
    for e in views.derived_shared_mechanism(kb, nodes):
        L.append(f"- {e['src']} ↔ {e['dst']} 共享机制 `{e['props']['mechanism']}`（不同领域；Agent Interpretation）")
    for t in kb.nodes("TransferHypothesis"):
        c = t["props"].get("comparison") or {}
        a = (t["props"].get("applicability") or {}).get("summary") or {}
        L.append(f"- 迁移假设 `{t['id']}`：structural={c.get('structural_similarity')}，lexical="
                 f"{c.get('lexical_similarity')}，flags={c.get('flags')}，假设违反 {a.get('violated', '?')}/"
                 f"未知 {a.get('unknown', '?')} — **{ep.label(t['status'])}**")
    L += ["", "## 6. 哪些性能差异来自评估协议", "", "使用 `cdri audit compare --results results.json` 生成可比性矩阵后粘贴；"
          "不可比的数字不得排序。", "", "## 7. 综合判断", "", AGENT, ""]
    cov = views.coverage(kb)
    L += ["## 8. 知识覆盖与缺口", "", f"- 论文 {cov['papers']}；阅读深度 {cov['reading_depth']}；时间分布 {cov['recency']}"]
    L += [f"- {g}" for g in cov["gaps"]]
    return "\n".join(L) + "\n"


def transfer_report(kb: KnowledgeBase, project: Optional[str] = None) -> str:
    pdata = proj.load(project)
    L = [f"# Cross-Domain Transfer Opportunities：{pdata.get('name')}", "", LEGEND,
         "> 所有迁移候选均为 **Hypothesis**：结构相似 ≠ 迁移有效。", ""]
    ts = kb.nodes("TransferHypothesis")
    if not ts:
        L.append("（尚无迁移候选；运行 `cdri transfer scan`）")
    for t in ts:
        p = t["props"]
        c = p.get("comparison") or {}
        a = p.get("applicability") or {}
        L += [f"## {p.get('method')} → {p.get('problem')}", "",
              f"- structural_similarity={c.get('structural_similarity')}（facet coverage {c.get('facet_coverage')}），"
              f"lexical_similarity={c.get('lexical_similarity')}", f"- flags：{c.get('flags')}",
              f"- 目标问题可引入的新机制：{c.get('new_mechanisms_for_target')}", "", "| 分面 | 得分 | 共享元素 |", "|---|---|---|"]
        for f, v in (c.get("facets") or {}).items():
            L.append(f"| {f} | {v.get('score')} | {', '.join(v.get('shared') or [])} |")
        if a:
            L += ["", "**假设适用性**", ""]
            for r in a.get("assumptions", []):
                L.append(f"- `{r['assumption']}`（来自 {r['origin']}）：**{r['state']}**" + (f" — {r['note']}" if r.get("note") else ""))
            L += ["", "**Negative Transfer Risk**", ""]
            L += [f"- {r['type']}：{r['detail']} → {r['implication']}" for r in a.get("negative_transfer_risks", [])] or ["- 未识别（不代表没有风险）"]
            if a.get("unknown_to_check"):
                L.append(f"- 待核查：{', '.join(a['unknown_to_check'])}")
        L += ["", "**为什么这种联系值得研究 / 不值得研究**", "", AGENT, ""]
    return "\n".join(L) + "\n"


def write(text: str, name: str, project: Optional[str] = None) -> Path:
    d = config.project_dir(project) / "exports"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p

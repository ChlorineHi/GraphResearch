"""Natural-language request -> mode routing. Explicit modes always win. The router suggests; the agent may
override with a stated reason. Rules are transparent keyword lists (zh + en) so routing can be audited."""

from __future__ import annotations

import re
from typing import Dict, List

MODES = ["landscape", "paper", "compare", "transfer", "diagnose", "audit", "graph", "ideate", "story", "refresh"]

RULES: Dict[str, List[str]] = {
    "diagnose": ["泛化差", "泛化很差", "低于简单基线", "低于基线", "不如基线", "不收敛", "训练正常", "瓶颈", "失败",
                 "loss", "plateau", "overfit", "过拟合", "collapse", "坍缩", "worse than baseline", "fails to generalize",
                 "poor generalization", "doesn't converge", "not converging", "underperform", "复现失败", "性能停滞",
                 "预测趋同", "debug", "诊断"],
    "audit": ["数据泄漏", "泄漏", "leakage", "可比", "comparab", "指标定义", "metric", "数据来源", "provenance", "审计",
              "audit", "基准公平", "fair benchmark", "split", "划分", "批次效应", "batch effect", "evaluation protocol",
              "评估协议"],
    "transfer": ["其他学科", "其他领域", "跨领域", "跨学科", "迁移", "借鉴", "cross-domain", "cross domain",
                 "other fields", "other disciplines", "borrow", "transfer", "analog", "类比", "同构"],
    "story": ["叙事", "故事", "story", "narrative", "写论文", "论文框架", "投稿", "贡献", "反例", "噪声上限",
              "noise ceiling", "局限", "提升有限", "negative result", "负面结果", "counterexample", "contribution"],
    "ideate": ["idea", "想法", "创新点", "研究假设", "假设", "brainstorm", "头脑风暴", "新方向", "hypothesis"],
    "compare": ["比较", "对比", "compare", "versus", " vs ", "区别", "差异", "异同"],
    "paper": ["精读", "这篇论文", "这篇文章", "read the paper", "deep read", "论文方法", "代码实现", "公式",
              "implementation", "method section"],
    "graph": ["知识图谱", "图谱", "knowledge graph", "知识库", "已有知识", "lineage", "来源追溯", "谱系", "复用",
              "之前读过", "跨项目", "previous project"],
    "refresh": ["更新", "新进展", "refresh", "since last", "最近有什么", "跟踪", "watch", "订阅"],
    "landscape": ["调研", "综述", "survey", "landscape", "最新", "现状", "review", "相关工作", "related work",
                  "state of the art", "sota", "研究进展", "文献"],
}
IDENT = re.compile(r"(10\.\d{4,9}/\S+|arxiv[: ]\d{4}\.\d{4,5}|\b\d{4}\.\d{4,5}(v\d+)?\b|pmid[: ]?\d+|PMC\d+)", re.I)
INTENSITY = {"quick": ["快速", "简要", "大致", "quick", "brief", "overview"],
             "deep": ["深入", "系统", "全面", "详细", "彻底", "deep", "thorough", "comprehensive", "systematic"]}
EXPLICIT = re.compile(r"^\s*(?:/cdri\s+|cdri\s+|mode\s*[:=]\s*|模式\s*[:：]\s*)(" + "|".join(MODES) + r")\b", re.I)


def route(text: str) -> dict:
    m = EXPLICIT.match(text)
    intensity = "standard"
    for lvl, kws in INTENSITY.items():
        if any(k in text.lower() for k in kws):
            intensity = lvl
    if m:
        return {"mode": m.group(1).lower(), "explicit": True, "secondary": [], "intensity": intensity,
                "reasons": ["explicit mode in request"], "commands": _commands(m.group(1).lower())}
    t = " " + text.lower() + " "
    scores: Dict[str, List[str]] = {}
    for mode, kws in RULES.items():
        hits = [k for k in kws if k.lower() in t]
        if hits:
            scores[mode] = hits
    if IDENT.search(text):
        scores.setdefault("paper", []).append("paper identifier")
    if not scores:
        return {"mode": "landscape", "explicit": False, "secondary": [], "intensity": intensity,
                "reasons": ["no rule matched; default to landscape (ask the user if the goal is unclear)"],
                "commands": _commands("landscape")}
    priority = ["diagnose", "transfer", "audit", "story", "graph", "ideate", "compare", "paper", "refresh", "landscape"]
    ordered = sorted(scores, key=lambda k: (-len(scores[k]), priority.index(k)))
    # problem-solving modes outrank generic survey words when both appear
    for strong in ("diagnose", "transfer", "story", "graph", "audit"):
        if strong in scores and ordered[0] == "landscape":
            ordered.remove(strong)
            ordered.insert(0, strong)
            break
    primary = ordered[0]
    return {"mode": primary, "explicit": False, "secondary": ordered[1:3], "intensity": intensity,
            "reasons": [f"{k}: {scores[k]}" for k in ordered], "commands": _commands(primary)}


def _commands(mode: str) -> List[str]:
    return {
        "landscape": ["cdri landscape plan \"<topic>\" --abstraction \"<abstract problem>\"",
                      "cdri landscape run --plan <plan.json> | cdri landscape run \"<topic>\"",
                      "cdri screen suggest --run <id>", "cdri report landscape --run <id>"],
        "paper": ["cdri paper fetch <id>", "cdri paper read <id> --plan", "cdri paper section <id> methods",
                  "cdri code locate <id>", "cdri paper card-template", "cdri paper ingest card.json"],
        "compare": ["cdri compare methods <method:a> <method:b>", "cdri audit compare --results results.json"],
        "transfer": ["cdri project problem problem.json", "cdri transfer scan", "cdri transfer check <method> --facts",
                     "cdri transfer record <method> <problem>", "cdri report transfer"],
        "diagnose": ["cdri diagnose log train.csv", "cdri diagnose triage \"<symptom>\" --attempts N --done ...",
                     "cdri diagnose conclude <id> ...", "cdri experiment record ..."],
        "audit": ["cdri audit leakage data.csv --split split --group ...", "cdri audit metric preds.csv ...",
                  "cdri audit compare --results results.json", "cdri audit provenance --profile single_cell"],
        "graph": ["cdri kg search \"<q>\" --mode mechanism|semantic|keyword", "cdri graph lineage <idea:...>",
                  "cdri graph export --view mechanism --format html", "cdri graph coverage"],
        "ideate": ["cdri ideate scaffold --from <transfer:...>", "cdri ideate add idea.json"],
        "story": ["cdri story scaffold", "cdri story check story.json"],
        "refresh": ["cdri refresh add \"<topic>\"", "cdri refresh run <watch>"],
    }[mode]

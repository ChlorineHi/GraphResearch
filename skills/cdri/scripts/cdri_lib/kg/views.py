"""Graph views (citation, mechanism, transfer, problem-limitation, evidence, lineage, coverage) and exporters
(Mermaid, Graphviz DOT, standalone HTML, GraphML, JSON). Edge styling encodes epistemic status."""

from __future__ import annotations

import html
import json
from collections import deque
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import epistemics as ep
from .store import KnowledgeBase

VIEWS = {
    "citation": ({"Paper"}, {"CITES", "VERSION_OF"}),
    "mechanism": ({"Paper", "Method", "Mechanism", "Assumption", "MathematicalOperator", "Domain"},
                  {"USES_METHOD", "USES_MECHANISM", "SUBCLASS_OF", "DEPENDS_ON_ASSUMPTION", "SHARES_MECHANISM_WITH",
                   "USES_OPERATOR", "IN_DOMAIN"}),
    "transfer": ({"Method", "Mechanism", "ResearchProblem", "TransferHypothesis", "Domain", "Assumption", "Paper",
                  "ResearchIdea", "Project"},
                 {"POTENTIALLY_TRANSFERS_TO", "INSPIRES_HYPOTHESIS", "IN_DOMAIN", "USES_MECHANISM",
                  "VIOLATES_ASSUMPTION", "SATISFIES_ASSUMPTION", "LINKS_TO", "USES_METHOD"}),
    "problem-limitation": ({"ResearchProblem", "Method", "Limitation", "FailureMode", "Paper", "Diagnosis"},
                           {"SOLVES", "HAS_LIMITATION", "EXPLAINS_FAILURE", "HAS_FAILURE_MODE"}),
    "evidence": ({"Project", "LocalExperiment", "Diagnosis", "FailureMode", "ScientificClaim", "ResearchIdea",
                  "TransferHypothesis", "Paper", "ResearchProblem", "Method"},
                 {"SUPPORTS", "CONTRADICTS", "TESTS", "EXPLAINS_FAILURE", "INSPIRES_HYPOTHESIS", "PART_OF_PROJECT",
                  "LINKS_TO", "HAS_FAILURE_MODE", "POTENTIALLY_TRANSFERS_TO"}),
}
COLORS = {"Paper": "#4e79a7", "Method": "#f28e2b", "Mechanism": "#e15759", "Assumption": "#76b7b2",
          "ResearchProblem": "#59a14f", "TransferHypothesis": "#edc948", "ResearchIdea": "#b07aa1",
          "LocalExperiment": "#ff9da7", "FailureMode": "#9c755f", "Limitation": "#bab0ac", "Domain": "#86bcb6",
          "Project": "#d37295", "Diagnosis": "#a0cbe8", "ScientificClaim": "#8cd17d",
          "MathematicalOperator": "#ffbe7d"}
WEAK = {"hypothesis", "agent_inference", "unverified"}


def subgraph(kb: KnowledgeBase, view: str, focus: Optional[str] = None, depth: int = 2,
             limit: int = 400) -> Tuple[Dict[str, dict], List[dict]]:
    ntypes, etypes = VIEWS[view]
    edges = [e for e in kb.edges() if e["type"] in etypes]
    nodes: Dict[str, dict] = {}
    if focus:
        keep = _neighborhood(edges, focus, depth)
        edges = [e for e in edges if e["src"] in keep and e["dst"] in keep]
    for e in edges:
        for nid in (e["src"], e["dst"]):
            if nid not in nodes:
                n = kb.get_node(nid)
                if n and n["type"] in ntypes:
                    nodes[nid] = n
    edges = [e for e in edges if e["src"] in nodes and e["dst"] in nodes]
    if view == "mechanism":
        edges += derived_shared_mechanism(kb, nodes)
    return dict(list(nodes.items())[:limit]), edges[: limit * 3]


def derived_shared_mechanism(kb: KnowledgeBase, nodes: Dict[str, dict]) -> List[dict]:
    """Methods from different domains that use the same mechanism (computed, not stored)."""
    out = []
    by_mech: Dict[str, List[str]] = {}
    for e in kb.edges(etype="USES_MECHANISM"):
        if e["src"].startswith("method:"):
            by_mech.setdefault(e["dst"], []).append(e["src"])
    for mech, methods in by_mech.items():
        doms = {m: {x["dst"] for x in kb.edges(src=m, etype="IN_DOMAIN")} for m in methods}
        for i in range(len(methods)):
            for j in range(i + 1, len(methods)):
                a, b = methods[i], methods[j]
                if a in nodes and b in nodes and doms[a] and doms[b] and not (doms[a] & doms[b]):
                    out.append({"id": f"derived:{a}|{b}|{mech}", "src": a, "dst": b, "type": "SHARES_MECHANISM_WITH",
                                "status": "agent_inference", "props": {"mechanism": mech, "derived": True}})
    return out


def _neighborhood(edges: List[dict], focus: str, depth: int) -> Set[str]:
    adj: Dict[str, Set[str]] = {}
    for e in edges:
        adj.setdefault(e["src"], set()).add(e["dst"])
        adj.setdefault(e["dst"], set()).add(e["src"])
    seen = {focus}
    q = deque([(focus, 0)])
    while q:
        n, d = q.popleft()
        if d >= depth:
            continue
        for m in adj.get(n, ()):
            if m not in seen:
                seen.add(m)
                q.append((m, d + 1))
    return seen


def lineage(kb: KnowledgeBase, node_id: str, depth: int = 5) -> Tuple[Dict[str, dict], List[dict]]:
    """Everything an idea / transfer hypothesis / failure mode was derived from (reverse traversal)."""
    skip = {"AUTHORED_BY", "PUBLISHED_IN", "PART_OF_PROJECT", "VERSION_OF", "CITES"}
    nodes: Dict[str, dict] = {}
    edges: List[dict] = []
    start = kb.get_node(node_id)
    if not start:
        raise KeyError(node_id)
    nodes[node_id] = start
    q = deque([(node_id, 0)])
    while q:
        nid, d = q.popleft()
        if d >= depth:
            continue
        for e in kb.edges(dst=nid):
            if e["type"] in skip:
                continue
            edges.append(e)
            if e["src"] not in nodes:
                n = kb.get_node(e["src"])
                if n:
                    nodes[e["src"]] = n
                    q.append((e["src"], d + 1))
    for nid in list(nodes):
        if nid.startswith("method:"):
            for e in kb.edges(src=nid, etype="IN_DOMAIN"):
                n = kb.get_node(e["dst"])
                if n:
                    nodes[e["dst"]] = n
                    edges.append(e)
    return nodes, edges


def coverage(kb: KnowledgeBase, topic: Optional[str] = None) -> dict:
    papers = kb.nodes("Paper")
    if topic:
        ids = {h["id"] for h in kb.search_nodes(topic, ["Paper"], k=500)}
        papers = [p for p in papers if p["id"] in ids]
    depth: Dict[str, int] = {}
    for p in papers:
        d = p["props"].get("reading_depth", "metadata")
        depth[d] = depth.get(d, 0) + 1
    mech_domains: Dict[str, Dict[str, int]] = {}
    for e in kb.edges(etype="USES_MECHANISM"):
        if not e["src"].startswith("method:"):
            continue
        doms = [x["dst"].split(":", 1)[1] for x in kb.edges(src=e["src"], etype="IN_DOMAIN")] or ["(no domain)"]
        for d in doms:
            mech_domains.setdefault(e["dst"].split(":", 1)[1], {}).setdefault(d, 0)
            mech_domains[e["dst"].split(":", 1)[1]][d] += 1
    gaps = []
    for m, doms in mech_domains.items():
        if len(doms) == 1:
            gaps.append(f"mechanism '{m}' only seen in domain {list(doms)[0]}: cross-domain evidence missing")
    probs = kb.nodes("ResearchProblem")
    unsolved = [p["label"] for p in probs if not kb.edges(dst=p["id"], etype="SOLVES")]
    recency: Dict[str, int] = {}
    for p in papers:
        r = (p["props"].get("signals") or {}).get("recency", "unknown")
        recency[r] = recency.get(r, 0) + 1
    if depth.get("deep", 0) == 0 and papers:
        gaps.append("no paper read at depth=deep in this scope")
    if recency.get("recent", 0) == 0 and papers:
        gaps.append("no recent (within window) papers in this scope")
    return {"papers": len(papers), "reading_depth": depth, "recency": recency, "mechanism_by_domain": mech_domains,
            "problems_without_solving_method": unsolved[:30], "gaps": gaps,
            "edge_status": _edge_status(kb)}


def _edge_status(kb: KnowledgeBase) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for e in kb.edges():
        out[e["status"]] = out.get(e["status"], 0) + 1
    return out


# ---------------- exporters ----------------
def _short(s: str, n: int = 48) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def to_mermaid(nodes: Dict[str, dict], edges: List[dict]) -> str:
    ids = {nid: f"n{i}" for i, nid in enumerate(nodes)}
    out = ["flowchart LR"]
    for nid, n in nodes.items():
        label = _short(n["label"]).replace('"', "'")
        out.append(f'  {ids[nid]}["{n["type"]}: {label}<br/><small>{ep.label(n["status"])}</small>"]')
    for e in edges:
        if e["src"] in ids and e["dst"] in ids:
            arrow = "-.->" if e["status"] in WEAK else "-->"
            out.append(f'  {ids[e["src"]]} {arrow}|{e["type"]}| {ids[e["dst"]]}')
    used = sorted({n["type"] for n in nodes.values()})
    for t in used:
        cls = t.lower()
        out.append(f"  classDef {cls} fill:{COLORS.get(t, '#dddddd')},color:#111;")
        members = ",".join(ids[k] for k, n in nodes.items() if n["type"] == t)
        out.append(f"  class {members} {cls};")
    return "\n".join(out) + "\n"


def to_dot(nodes: Dict[str, dict], edges: List[dict]) -> str:
    out = ["digraph cdri {", "  rankdir=LR; node [shape=box, style=filled, fontname=Helvetica];"]
    for nid, n in nodes.items():
        out.append(f'  "{nid}" [label="{n["type"]}\\n{_short(n["label"]).replace(chr(34), chr(39))}\\n'
                   f'({ep.label(n["status"])})", fillcolor="{COLORS.get(n["type"], "#dddddd")}"];')
    for e in edges:
        style = "dashed" if e["status"] in WEAK else "solid"
        out.append(f'  "{e["src"]}" -> "{e["dst"]}" [label="{e["type"]}", style={style}];')
    out.append("}")
    return "\n".join(out) + "\n"


def to_json(nodes: Dict[str, dict], edges: List[dict]) -> str:
    return json.dumps({"nodes": [{"id": k, "type": v["type"], "label": v["label"], "status": v["status"],
                                  "scope": v.get("scope")} for k, v in nodes.items()],
                       "links": [{"source": e["src"], "target": e["dst"], "type": e["type"], "status": e["status"]}
                                 for e in edges]}, indent=2, ensure_ascii=False)


def to_graphml(nodes: Dict[str, dict], edges: List[dict]) -> str:
    esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '<key id="type" for="node" attr.name="type" attr.type="string"/>',
           '<key id="label" for="node" attr.name="label" attr.type="string"/>',
           '<key id="status" for="all" attr.name="status" attr.type="string"/>',
           '<key id="etype" for="edge" attr.name="type" attr.type="string"/>',
           '<graph id="cdri" edgedefault="directed">']
    for k, v in nodes.items():
        out.append(f'<node id="{esc(k)}"><data key="type">{esc(v["type"])}</data><data key="label">'
                   f'{esc(v["label"])}</data><data key="status">{esc(v["status"])}</data></node>')
    for i, e in enumerate(edges):
        out.append(f'<edge id="e{i}" source="{esc(e["src"])}" target="{esc(e["dst"])}"><data key="etype">'
                   f'{esc(e["type"])}</data><data key="status">{esc(e["status"])}</data></edge>')
    out += ["</graph>", "</graphml>"]
    return "\n".join(out) + "\n"


def to_html(nodes: Dict[str, dict], edges: List[dict], title: str = "CDRI knowledge graph") -> str:
    data = json.loads(to_json(nodes, edges))
    for n in data["nodes"]:
        n["color"] = COLORS.get(n["type"], "#cccccc")
        n["status_label"] = ep.label(n["status"])
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:system-ui,sans-serif;margin:0}}#info{{position:fixed;top:8px;left:8px;background:#fff;
padding:8px 12px;border:1px solid #ccc;max-width:420px;font-size:13px}}svg{{width:100vw;height:100vh}}
.weak{{stroke-dasharray:5,4}}text{{font-size:10px;pointer-events:none}}</style></head><body>
<div id="info"><b>{html.escape(title)}</b><br>Dashed edge = hypothesis / agent inference / unverified.
Drag nodes; hover for details.<div id="d"></div></div><svg id="s"></svg>
<script>
const G={payload};
const W=innerWidth,H=innerHeight,svg=document.getElementById('s');
const N=G.nodes.map((n,i)=>Object.assign(n,{{x:W/2+Math.cos(i)*200*Math.random(),y:H/2+Math.sin(i)*200*Math.random(),vx:0,vy:0}}));
const idx=Object.fromEntries(N.map((n,i)=>[n.id,i]));
const L=G.links.filter(l=>l.source in idx&&l.target in idx);
function tick(){{for(const a of N){{for(const b of N){{if(a===b)continue;let dx=a.x-b.x,dy=a.y-b.y,d=Math.max(25,Math.hypot(dx,dy));
let f=2200/(d*d);a.vx+=dx/d*f;a.vy+=dy/d*f;}}}}
for(const l of L){{const a=N[idx[l.source]],b=N[idx[l.target]];let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,f=(d-120)*0.01;
a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f;}}
for(const n of N){{if(n.fixed)continue;n.vx+=(W/2-n.x)*0.002;n.vy+=(H/2-n.y)*0.002;n.x+=n.vx*=0.6;n.y+=n.vy*=0.6;}}}}
for(let i=0;i<300;i++)tick();
const ns='http://www.w3.org/2000/svg';
const lines=L.map(l=>{{const e=document.createElementNS(ns,'line');e.setAttribute('stroke','#999');
if(['hypothesis','agent_inference','unverified'].includes(l.status))e.classList.add('weak');svg.appendChild(e);return e;}});
const circ=N.map(n=>{{const g=document.createElementNS(ns,'g');const c=document.createElementNS(ns,'circle');c.setAttribute('r',8);
c.setAttribute('fill',n.color);const t=document.createElementNS(ns,'text');t.textContent=n.label.slice(0,40);t.setAttribute('x',10);
g.appendChild(c);g.appendChild(t);svg.appendChild(g);
g.onmouseover=()=>document.getElementById('d').innerHTML='<hr><b>'+n.type+'</b>: '+n.label.replace(/</g,'&lt;')+'<br>id: '+n.id+'<br>status: '+n.status_label;
g.onmousedown=ev=>{{n.fixed=true;const mv=e=>{{n.x=e.clientX;n.y=e.clientY;draw();}};addEventListener('mousemove',mv);
addEventListener('mouseup',()=>removeEventListener('mousemove',mv),{{once:true}});}};return g;}});
function draw(){{L.forEach((l,i)=>{{const a=N[idx[l.source]],b=N[idx[l.target]];const e=lines[i];e.setAttribute('x1',a.x);e.setAttribute('y1',a.y);
e.setAttribute('x2',b.x);e.setAttribute('y2',b.y);}});N.forEach((n,i)=>circ[i].setAttribute('transform','translate('+n.x+','+n.y+')'));}}
draw();
</script></body></html>
"""


EXPORTERS = {"mermaid": to_mermaid, "dot": to_dot, "json": to_json, "graphml": to_graphml, "html": to_html}

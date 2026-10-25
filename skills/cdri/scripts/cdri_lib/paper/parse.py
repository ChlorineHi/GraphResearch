"""HTML / JATS XML / PDF -> Markdown, and section segmentation with section 'kind' labels."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KIND_PATTERNS = [
    ("abstract", r"^abstract$|^summary$"),
    ("introduction", r"introduction|^background$"),
    ("methods", r"method|materials and methods|online methods|approach|model architecture|^model$|our model|"
                r"framework|algorithm|problem (setup|formulation)|preliminar|formulation"),
    ("experiments", r"experiment|evaluation|benchmark|setup"),
    ("results", r"^results?|results and discussion|findings"),
    ("ablation", r"ablation"),
    ("discussion", r"discussion|conclusion"),
    ("limitations", r"limitation|broader impact|failure"),
    ("supplementary", r"supplement|supporting information|extended data"),
    ("appendix", r"appendix|^[a-h](\.\d+)?\s|^appendices"),
    ("data_availability", r"data availability|code availability|availability"),
    ("references", r"^references$|^bibliography$|literature cited"),
]


def section_kind(title: str) -> str:
    t = re.sub(r"^[\dIVX]+(\.\d+)*\.?\s+", "", title.strip().lower())
    for kind, pat in KIND_PATTERNS:
        if re.search(pat, t):
            return kind
    return "other"


# ---------------- HTML ----------------
class _HTML2MD(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "button", "form"}
    BLOCK = {"p", "div", "section", "article", "li", "tr", "figcaption", "caption", "blockquote", "dd", "dt"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.skip = 0
        self.heading: Optional[int] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "math" and a.get("alttext"):
            self.out.append(f" ${a['alttext']}$ ")
            self.skip += 1
            self._math = True
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = int(tag[1])
            self.out.append("\n\n" + "#" * self.heading + " ")
        elif tag in self.BLOCK:
            self.out.append("\n\n" if tag != "li" else "\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag == "br":
            self.out.append("\n")
        elif tag == "a" and a.get("href", "").startswith("http") and "github.com" in a.get("href", ""):
            self.out.append(f" <{a['href']}> ")

    def handle_endtag(self, tag):
        if tag in self.SKIP or (tag == "math" and getattr(self, "_math", False)):
            if self.skip:
                self.skip -= 1
            if tag == "math":
                self._math = False
            return
        if self.skip:
            return
        if self.heading and re.fullmatch(r"h[1-6]", tag):
            self.heading = None
            self.out.append("\n\n")

    def handle_data(self, data):
        if self.skip:
            return
        txt = re.sub(r"\s+", " ", data)
        if self.heading:
            txt = txt.replace("\n", " ")
        self.out.append(txt)


def html_to_md(html: str) -> str:
    p = _HTML2MD()
    p.feed(html)
    md = "".join(p.out)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# ---------------- JATS ----------------
def _itertext(el) -> str:
    parts = []
    for node in el.iter():
        tag = node.tag.split("}")[-1]
        if tag == "tex-math" and node.text:
            parts.append(f" ${node.text.strip()}$ ")
            continue
        if node.text and tag not in ("tex-math",):
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def jats_to_md(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)  # noqa: S314 - Europe PMC JATS, no external entities resolved
    out: List[str] = []
    title = root.find(".//article-title")
    if title is not None:
        out.append(f"# {_itertext(title)}\n")
    ab = root.find(".//abstract")
    if ab is not None:
        out.append("## Abstract\n\n" + _itertext(ab) + "\n")

    def walk(sec, level):
        t = sec.find("title")
        if t is not None:
            out.append("\n" + "#" * min(level, 6) + " " + _itertext(t) + "\n")
        for ch in sec:
            tag = ch.tag.split("}")[-1]
            if tag == "sec":
                walk(ch, level + 1)
            elif tag == "p":
                out.append(_itertext(ch) + "\n")
            elif tag in ("fig", "table-wrap"):
                cap = ch.find(".//caption")
                lab = ch.find("label")
                out.append(f"\n> **{_itertext(lab) if lab is not None else tag}** "
                           f"{_itertext(cap) if cap is not None else ''}\n")
            elif tag == "disp-formula":
                out.append(f"\n$$ {_itertext(ch)} $$\n")
            elif tag == "supplementary-material":
                out.append(f"\n> Supplementary: {_itertext(ch)}\n")
            elif tag == "list":
                for li in ch.iter():
                    if li.tag.split('}')[-1] == "list-item":
                        out.append("- " + _itertext(li))
    body = root.find(".//body")
    if body is not None:
        for sec in body:
            if sec.tag.split("}")[-1] == "sec":
                walk(sec, 2)
            elif sec.tag.split("}")[-1] == "p":
                out.append(_itertext(sec) + "\n")
    back = root.find(".//back")
    if back is not None:
        for sec in back.iter():
            tag = sec.tag.split("}")[-1]
            if tag in ("app", "sec") and sec.find("title") is not None:
                walk(sec, 2)
        refs = back.find(".//ref-list")
        if refs is not None:
            out.append("\n## References\n")
            for ref in refs.findall(".//ref"):
                out.append("- " + _itertext(ref))
    return "\n".join(out).strip() + "\n"


# ---------------- PDF ----------------
HEADING_LINE = re.compile(
    r"^(?:(\d+(?:\.\d+){0,3})\.?\s+([A-Z][A-Za-z0-9 ,:;&()\-/]{2,80})|"
    r"(Abstract|Introduction|Background|Methods|Materials and Methods|Online Methods|Results|Discussion|"
    r"Conclusions?|Limitations|References|Acknowledgements?|Supplementary (?:Information|Materials?|Note \d+)|"
    r"Appendix(?: [A-H])?|Data availability|Code availability))\s*$")


def pdf_to_md(path: Path) -> Tuple[str, str]:
    """Return (markdown, parser_name). Raises RuntimeError when no PDF backend is installed."""
    try:
        import pymupdf4llm  # type: ignore
        return pymupdf4llm.to_markdown(str(path)), "pymupdf4llm"
    except ImportError:
        pass
    try:
        import fitz  # type: ignore  # PyMuPDF
    except ImportError:
        fitz = None
    pages: List[str] = []
    if fitz is not None:
        doc = fitz.open(str(path))
        pages = [pg.get_text("text") for pg in doc]
        doc.close()
        parser = "pymupdf"
    else:
        try:
            from pypdf import PdfReader  # type: ignore
            pages = [pg.extract_text() or "" for pg in PdfReader(str(path)).pages]
            parser = "pypdf"
        except ImportError:
            import shutil
            import subprocess
            if not shutil.which("pdftotext"):
                raise RuntimeError("no PDF backend: install pymupdf / pymupdf4llm / pypdf or poppler pdftotext")
            txt = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True,
                                 timeout=180).stdout
            pages = txt.split("\f")
            parser = "pdftotext"
    out = []
    for i, txt in enumerate(pages, 1):
        out.append(f"\n<!-- page {i} -->\n")
        txt = re.sub(r"-\n(?=[a-z])", "", txt)
        for line in txt.splitlines():
            s = line.strip()
            m = HEADING_LINE.match(s)
            if m and len(s) < 90:
                num = m.group(1)
                level = 2 + (num.count(".") if num else 0)
                out.append("\n" + "#" * min(level, 6) + " " + s + "\n")
            else:
                out.append(line)
    return "\n".join(out), parser


# ---------------- sections ----------------
def sections(md: str) -> List[Dict[str, object]]:
    lines = md.splitlines()
    heads: List[Tuple[int, int, str]] = []
    page = 1
    pages_at: Dict[int, int] = {}
    for i, ln in enumerate(lines, 1):
        pm = re.match(r"<!-- page (\d+) -->", ln.strip())
        if pm:
            page = int(pm.group(1))
        pages_at[i] = page
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", ln)
        if m and len(m.group(2)) < 160:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    out: List[Dict[str, object]] = []
    for k, (ln, lvl, title) in enumerate(heads):
        end = len(lines)
        for ln2, lvl2, _ in heads[k + 1:]:
            if lvl2 <= lvl:
                end = ln2 - 1
                break
        nxt = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        kind = section_kind(title)
        out.append({"idx": k, "title": title, "level": lvl, "kind": kind, "start": ln, "end": end,
                    "own_end": nxt, "chars": sum(len(x) for x in lines[ln - 1:end]),
                    "page": pages_at.get(ln)})
    # children inherit the kind of a typed parent (e.g. "3.2 Loss" under "3 Methods")
    for s in out:
        if s["kind"] == "other":
            for p in out:
                if p["level"] < s["level"] and p["start"] < s["start"] <= p["end"] and p["kind"] != "other":
                    s["kind"] = p["kind"]
    return out


def chunk(md: str, secs: List[Dict[str, object]], size: int = 1200) -> List[Tuple[str, str]]:
    lines = md.splitlines()
    out: List[Tuple[str, str]] = []
    bounds = [(int(s["start"]), int(s["own_end"]), str(s["title"])) for s in secs] or [(1, len(lines), "")]
    if bounds[0][0] > 1:
        bounds.insert(0, (1, bounds[0][0] - 1, "front matter"))
    for a, b, title in bounds:
        buf = ""
        for para in re.split(r"\n\s*\n", "\n".join(lines[a - 1:b])):
            para = para.strip()
            if not para:
                continue
            if buf and len(buf) + len(para) > size:
                out.append((title, buf))
                buf = para
            else:
                buf = f"{buf}\n\n{para}" if buf else para
        if buf:
            out.append((title, buf))
    return out

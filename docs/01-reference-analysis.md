# 第一阶段：开源 Research Skills 深度研究与复用分析

> 分析日期：2026-10-25。所有结论基于对仓库源码（`SKILL.md`、`scripts/`、`references/`）的实际阅读，
> 克隆版本为各仓库默认分支的 `--depth 1` 快照（本地路径 `_refs/`，不随项目分发）。
> 四个仓库均为 **MIT License**，允许在保留版权声明的前提下复用代码与思想（见 `THIRD_PARTY_NOTICES.md`）。

## 1. 逐仓库实现分析

### 1.1 jxtse/scientific-research-skills

| Skill | 实际实现 | 观察 |
|---|---|---|
| `literature-search` | **只有 `SKILL.md`**，引用的 `scripts/search/semantic-scholar.mjs`、`arxiv.mjs`、`search.mjs` 并不在仓库中 | 检索能力依赖外部 Node 脚本、Tavily/Exa/Gemini 等付费服务；排序规则为 `citation × recency × venue tier × relevance`，venue tier 直接作为质量代理 |
| `paper-reading` | 只有 `SKILL.md`（三级阅读模板 Quick/Standard/Deep） | 有"Hidden assumptions""Ablation reveals what matters"等好的阅读启发式，但没有任何机制强制 Agent 真正读过 Methods；没有代码层分析 |
| `related-work-survey` | 只有 `SKILL.md` | "Survey dimensions → taxonomy → gap → positioning" 的叙事框架可借鉴；"每轴收集 10–20 篇"属于固定数量 |
| `paper-fulltext-harvest` | **真实 Python 实现**（`clients.py` 58KB）：Elsevier/Wiley/Springer TDM API、Crossref TDM link、Unpaywall、OpenAlex OA；按 DOI 前缀路由 19 个出版商家族；浏览器 fallback | 工程成熟，但目标是"批量下载 PDF"，依赖机构 IP/Token；未做解析、去重或结构化；浏览器路线需用户登录 Chrome，存在合规风险，需要谨慎 |

**可复用**：DOI 前缀 → 出版商路由思想；OA 级联（Unpaywall → OpenAlex → Crossref）；
"TDM 需机构授权"的诚实说明。
**限制**：检索与阅读部分基本只是提示词；没有持久知识库；没有证据等级。

### 1.2 pinshuai/literature-review-skill

| 组件 | 实际实现 | 观察 |
|---|---|---|
| `SKILL.md`（38KB） | 完整的 PRISMA 风格流程：PICO、检索式、纳排标准、标题/摘要/全文筛选、主题综合、质量评估（Cochrane RoB、NOS、AMSTAR 2） | 方法学规范性强；**强制 30–50 篇最小语料**，与本任务"不要为凑数引入无关论文"相冲突 |
| `scripts/search_databases.py` | **不执行检索**，只对已有 JSON 结果做去重（DOI → 精确标题）、按 citation/year 排序、年份过滤、格式化 | 去重只用精确标题匹配，无版本关联；排序按引用数 |
| `scripts/verify_citations.py` | 用 `doi.org/api/handles` + Crossref 校验 DOI 存在性并取元数据 | 只验证"DOI 存在"，不验证 DOI 是否指向声称的论文 |
| `examples/wildfire-streamflow/sources/search_log.md` | 人工维护的检索日志 | 检索记录是 Markdown 自由文本，非结构化，无法程序化审计 |

**可复用**：检索日志字段设计（数据库、日期、检索式、结果数）；纳排标准记录；主题综合而非逐篇摘要的写作原则。
**限制**：检索本身依赖外部 `paper-search-mcp`（硬编码作者本机路径 `/Users/shuai/...`）；无知识图谱；无跨学科机制。

### 1.3 marciob/skill-research-papers

| 组件 | 实际实现 | 观察 |
|---|---|---|
| `scripts/fetch_and_parse.py`（55KB） | **最成熟的全文获取实现**：标识符解析（DOI/arXiv 新旧格式/PMID/PMCID/URL）→ 规范 ID；OA 级联 arXiv HTML → arXiv PDF → PMC XML → Unpaywall → OpenAlex `best_oa_location` → S2 `openAccessPdf` → Crossref TDM → DOI landing；HTML stub 检测；PDF 解析 pymupdf4llm → pymupdf → pdftotext；按规范 ID 缓存至 `~/.cache/research-papers/` | 每一步写入 `tried` 日志，失败可追溯 |
| **Read-plan + Sentinel 协议** | 解析结果末尾追加 `<!-- END-OF-PAPER:<sha> -->`，输出覆盖全文的 `read_plan`；SKILL.md 要求 Agent 引用 sentinel 才能综合 | 这是唯一一个用**机械手段**约束"不得只读摘要"的实现，非常值得复用 |
| `references/screening-rubric.md`、`smoke-tests.md` | 筛选打分维度；对各数据源在 headless 环境中实际可用性的冒烟记录 | "声称数据源可用前先做冒烟测试"的诚信原则 |
| 证据深度标签 | `[Full text]` / `[Abstract only — reason]` / `[Metadata only]` | 直接对应本任务的阅读深度区分 |

**可复用**：标识符解析正则、OA 级联顺序、read-plan + sentinel、证据深度标签、按规范 ID 缓存。
**限制**：Sentinel 只证明"读到了文件末尾"，不能区分哪些章节被真正用于哪条结论；无知识库；无代码分析。

### 1.4 KalarisLabs/research-agent-skills（大型 monorepo，约 3000 文件）

| Skill | 实际实现 | 观察 |
|---|---|---|
| `research-knowledge-graph` | `build_graph.py`：从 `.bib`/CSL-JSON 构图，可选 OpenAlex 富化；节点 `paper/author/venue/topic`，边 `authored_by/published_in/about/cites`；导出 NetworkX JSON、GraphML、Neo4j CSV、Obsidian vault | **只是书目/引用图**。没有方法、机制、假设、局限、代码等实体；没有来源追溯与证据等级；每次全量重建，不支持增量 |
| `paper-corpus-rag` | `paper_index.py`：SQLite FTS5 + BM25，按段落切块，保留最近章节标题，SHA256 增量重建索引，命中返回 `file#chunk` 引用句柄 | 轻量、零依赖、可引用，非常适合作为全文检索层 |
| `citation-verification` | `verify_citations.py`：Crossref + OpenAlex + arXiv 三源；**检查 DOI 是否指向不同论文**（标题相似度阈值 0.90/0.75）、年份、第一作者；无 DOI 时按标题+作者+年份综合打分 | 比 pinshuai 版本严格得多，正确处理了预印本仅存在于 arXiv 的情况 |
| `literature-review` | 与 pinshuai 版本同源（K-Dense），附加 schematic 生成 | — |
| `scientific-brainstorming` | `evaluate_matrix.py`：显式准则、权重、区间评分、敏感性分析；规则"不自动选出 winner"；标注 idea/assumption/prediction/located evidence/decision | 认识论标签与"不用单一分数"的原则与本任务高度一致 |
| `scientific-critical-thinking` | 纯参考文档：GRADE、Cochrane RoB、偏倚、统计陷阱、逻辑谬误 | 适合作为诊断与故事审查的检查清单来源 |
| `autoresearch` | 两层循环（inner 实验 / outer 综合）、`research-state.yaml` 状态文件、`/loop` 持续运行 | **"完全自主、不询问用户、Never stop"**，与本任务"不擅自更换方向、不大规模训练"的边界直接冲突；但状态文件 + 研究日志的断点恢复思路可借鉴 |

## 2. 横向能力对比

| 能力 | jxtse | pinshuai | marciob | KalarisLabs | 本项目需要 |
|---|---|---|---|---|---|
| 实际执行多库检索的代码 | ✗（脚本缺失） | ✗（依赖外部 MCP） | 部分（curl 指引） | ✗ | ✓ 统一适配器 |
| 结构化检索日志 | ✗ | Markdown 手写 | 文字建议 | ✗ | ✓ JSONL，含失败/限流 |
| 去重与版本关联 | 标题模糊 | DOI/精确标题 | DOI→ID→标题+年份 | ✗ | ✓ 预印本↔正式版 |
| 全文获取 | TDM 批量下载 | ✗ | ✓ OA 级联 + 解析 | ✗ | ✓（复用 marciob 思想） |
| 强制深读机制 | ✗ | ✗ | Sentinel | ✗ | ✓ Sentinel + 章节阅读台账 + 卡片校验 |
| 方法级结构化记录 | 模板 | 数据抽取表 | 抽取清单 | ✗ | ✓ Paper Card（A–E 五部分） |
| 公式 ↔ 代码映射 | ✗ | ✗ | ✗ | ✗ | ✓ |
| 知识图谱 | ✗ | ✗ | ✗ | 书目图 | ✓ 方法/机制/假设/局限 类型化图 |
| 来源追溯 + 认识论状态 | ✗ | ✗ | 证据深度标签 | 标签（仅头脑风暴） | ✓ 每条边绑定 provenance + 状态 |
| 跨学科机制迁移 | ✗ | ✗ | ✗ | ✗ | ✓ 核心创新 |
| 实验诊断 / 负面结果入库 | ✗ | ✗ | ✗ | autoresearch 记录 | ✓ |
| 指标可比性审计 | ✗ | ✗ | ✗ | ✗ | ✓ |
| 离线测试 | ✗ | ✗ | 冒烟脚本（在线） | 有 tests/ | ✓ Fixture |

## 3. 尚未解决的关键问题（本项目的设计切入点）

1. **"读过"无法验证到章节粒度**。Sentinel 只证明读到末尾；没有任何实现把"某条方法结论"绑定到"原文哪个章节/页码"。
   → 本项目：阅读台账（read ledger）记录实际读过的章节；Paper Card 中每个方法级断言必须携带 `source_location`，
   若来源章节不在台账中，CLI 自动将其降级为 `abstract_derived`/`unverified`。
2. **知识图谱只有书目关系**。现有图谱无法表达"论文 A 与论文 B 共享机制 X，而 X 依赖假设 Y，项目 Z 不满足 Y"。
   → 本项目：类型化节点（Method、MathematicalOperator、InductiveBias、Assumption…）与语义边，外加 Global/Project/Link 三层。
3. **Agent 推断会在后续会话中"升级"为事实**。没有任何实现区分作者主张、代码验证与 Agent 推断。
   → 本项目：每条知识都有 `epistemic_status`，普通写入**永不升级**状态；升级必须通过 `kg promote` 并提交非 Agent 来源的证据。
4. **跨学科检索不存在**。所有检索都是关键词驱动的领域内检索。
   → 本项目：四条检索通道（In-domain / Adjacent / Distant / Contradictory）+ 机制本体驱动的远域查询 + Method Signature 结构匹配。
5. **指标不可比被忽略**。所有 review skill 都会把不同论文的同名指标直接放进表格。
   → 本项目：指标本体 + 协议字段比较，输出 `Not Directly Comparable`。
6. **固定数量与自主性冲突**。pinshuai 强制 30–50 篇；autoresearch 要求永不停止、不询问用户。
   → 本项目：研究强度（Quick/Standard/Deep）只设置预算上限，不设下限；执行边界写入 SKILL.md 与 CLI（如拒绝覆盖冻结决策）。
7. **外部内容的提示注入**。没有实现把论文/仓库文本视为不可信输入。
   → 本项目：全文与代码缓存加"不可信内容"头，代码分析器只做静态解析，从不执行仓库代码。

## 4. 复用决策

| 来源 | 复用方式 | 理由 |
|---|---|---|
| marciob `fetch_and_parse.py` | **思想与算法重写**：标识符正则、OA 级联顺序、HTML stub 检测、read-plan + sentinel | 原脚本 55KB 单文件，耦合其缓存布局与 CLI；我们需要与统一数据模型（规范 ID、KG、台账）集成 |
| KalarisLabs `paper_index.py` | **算法复用**：FTS5 + BM25 + 段落切块 + 章节标题 + SHA 增量 | 直接适配为知识库全文层 |
| KalarisLabs `verify_citations.py` | **算法复用**：标题相似度阈值 0.90/0.75、年份±1、第一作者一致性、arXiv 兜底 | 用于检索结果元数据核验与报告引用核验 |
| KalarisLabs `build_graph.py` | 导出格式参考（GraphML、node-link JSON） | 我们的图谱 schema 完全不同 |
| KalarisLabs brainstorming | 原则复用：认识论标签、不选单一 winner、显式评价维度 | 写入 ideate 校验规则 |
| pinshuai | 检索日志字段、纳排理由记录 | 结构化为 JSONL |
| jxtse | DOI 前缀出版商路由、TDM 合规说明 | 作为全文获取的降级说明；不复用浏览器登录抓取 |
| autoresearch | 状态文件断点续作思想 | 改为 `session` 命令；**不**复用其自主运行策略 |

**不重新实现的成熟功能**：PDF 版面解析（依赖可选的 PyMuPDF / pymupdf4llm / pdftotext）、向量嵌入模型
（可选 `sentence-transformers`）、图分析算法（可选 NetworkX）。核心逻辑只依赖 Python 标准库。

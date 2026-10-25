# 第二阶段：CDRI 系统设计

## 0. 设计原则与职责划分

**Evidence Before Confidence · Mechanism Before Analogy · Reproducibility Before Performance Claims**

CDRI 由两部分组成，二者职责严格分离：

| 层 | 负责 | 不负责 |
|---|---|---|
| **Agent（LLM，由 `SKILL.md` 驱动）** | 理解论文、抽象机制、判断迁移适用性、撰写综合与叙事 | 声称执行过未执行的检索、绕过 CLI 校验写入知识 |
| **CLI（`cdri`，Python 标准库实现）** | 实际检索与记录、全文获取与章节切分、阅读台账、知识图谱存储与校验、结构匹配、日志与数据审计、指标重算、报告与可视化 | "理解"论文；CLI 只做可机械验证的事 |

关键点：**CLI 是 Agent 写入长期知识的唯一入口**。所有校验（来源位置、阅读台账、认识论状态、
禁止单一分数、冻结决策）都在 CLI 写入时执行，因此提示词之外还有机械约束。

## 1. 整体架构

```
                         ┌───────────── SKILL.md（路由 + 10 种模式工作流）─────────────┐
                         │ references/modes/*.md   references/*.md（规则、模板、本体说明）│
                         └───────────────────────────────┬───────────────────────────────┘
                                                         │ 调用
┌────────────────────────────────────── cdri CLI ───────▼──────────────────────────────────────┐
│ ① Retrieval Engine   planner(4 lanes) → router(discipline→sources) → sources/* → dedupe/versions │
│                      → screening(landscape/focused/deep) → run log (JSONL)                     │
│ ② Paper Understanding fulltext cascade → parse(HTML/JATS/PDF) → sections → read ledger         │
│                      → paper card (A–E + signature) validation → KG ingest                     │
│ ③ Code-to-Method     repo clone(pinned commit) → static AST roles → code map/permalinks        │
│                      → formula↔code links (consistent / discrepancy / unverified)              │
│ ④ Knowledge Graph    SQLite(global) + SQLite(project) + link layer; FTS5; provenance;          │
│                      epistemic status rules; alias resolution; traversal & lineage             │
│ ⑤ Transfer Engine    mechanism ontology + method signatures → structural matcher               │
│                      → applicability (assumptions vs project facts) → negative-transfer risk   │
│ ⑥ Diagnosis Engine   triage gate → taxonomy-ordered checks → log analysis → conclusions → KG    │
│ ⑦ Integrity Auditor  split/group/spatial leakage, provenance checklist, metric ontology,       │
│                      metric recomputation by aggregation level, benchmark comparability matrix │
│ ⑧ Insight & Story    hypothesis cards (9 fields, multi-dimension, no single score), story arc  │
│                      scaffold + evidence-status check                                          │
│ ⑨ Report Generator   landscape / deep method / transfer / synthesis / compare (中文 + English)  │
│ ⊕ graph export (Mermaid / Graphviz / HTML / GraphML / JSON) · refresh · session · route · config │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
          │ HTTP（缓存、限流、重试、fixture/offline）              │ 文件系统
   OpenAlex · S2 · Crossref · arXiv · PubMed · Europe PMC        $CDRI_HOME（全局）  <project>/.cdri（项目）
   (含 PMC / bioRxiv / medRxiv) · bioRxiv API · DBLP · GitHub
```

## 2. 组件职责

| 模块 | 代码 | 职责 |
|---|---|---|
| Research Retrieval Engine | `retrieval/` | 四通道检索计划；学科识别与数据源路由；7 个数据源适配器；去重与预印本↔正式版关联；发表状态判定；三级筛选；结构化检索日志 |
| Paper Understanding Engine | `paper/` | OA 全文级联；HTML/JATS/PDF → Markdown；章节识别（Methods/Results/Supplementary/Limitations…）；阅读台账；Paper Card 校验与入库 |
| Code-to-Method Analyzer | `codemap/` | 克隆并固定 commit；AST 静态识别模型/forward/loss/dataset/预处理/训练/评估/配置；稳定永久链接；公式↔代码映射入库 |
| Knowledge Graph Manager | `kg/` | 类型化节点/边；provenance；认识论状态；别名消歧；FTS5 全文；图遍历；机制相似检索；导出 |
| Cross-Domain Transfer Engine | `transfer/` | 机制本体（可扩展）；Method Signature；分面结构匹配 + 术语相似度对照；假设适用性；负迁移风险；已有迁移检查 |
| Experiment Diagnosis Engine | `diagnose/` | 琐碎错误过滤；症状 → 问题类型；按诊断顺序生成检查；日志曲线分析；结论与负面结果入库 |
| Data & Metric Integrity Auditor | `audit/` | 分组/重复/空间泄漏；数据来源清单；指标本体；按聚合层级重算指标；基准可比性矩阵 |
| Scientific Insight & Story Engine | `insight/` | 创新假设卡片校验；从知识图谱生成故事骨架；故事证据检查 |
| Research Report Generator | `report/` | 分层报告；证据标签；可追溯链接 |

## 3. 数据 Schema

### 3.1 规范标识符（`ids.py`）

| 类型 | 规范形式 | 示例 |
|---|---|---|
| 论文 | `paper:doi:<lower doi>` > `paper:arxiv:<id 无版本>` > `paper:pmid:<n>` > `paper:pmcid:PMC<n>` > `paper:openalex:W<n>` > `paper:title:<slug>-<year>` | `paper:arxiv:2106.01345` |
| arXiv DOI | `10.48550/arXiv.X` 归一为 `paper:arxiv:X` | |
| 其他实体 | `<type>:<slug>` | `mechanism:optimal-transport`、`assumption:exchangeable-samples` |
| 仓库 | `repo:github:<owner>/<name>` | |
| 代码模块 | `code:github:<owner>/<name>@<sha>:<path>::<symbol>` | |

多版本：预印本与正式版分别有节点，通过 `VERSION_OF` 边连接；`canonical` 属性指向正式版。

### 3.2 认识论状态（epistemic status）

| 状态 | 报告标签 | 允许的来源类型 |
|---|---|---|
| `verified` | Verified Fact | `metadata_api`（与登记处核验一致）、`paper_fulltext`（直接可核对的事实，如数据集名称） |
| `code_verified` | Verified Fact（代码） | `code`（固定 commit + 文件 + 行号） |
| `experiment_observed` | Verified Fact（本地实验） | `local_experiment`（存在的运行产物路径） |
| `author_claim` | Author Claim | `paper_fulltext` / `paper_supplement` / `paper_abstract` |
| `user_reported` | User Reported | `user` |
| `agent_inference` | Agent Interpretation | `agent` |
| `hypothesis` | Hypothesis | `agent` / `user` |
| `unverified` | Unsupported / Unverified | 任意（降级结果） |

**规则**（`kg/epistemics.py` 强制执行）：

1. 写入时，状态不得高于来源类型允许的上限（例如 `agent` 来源最高 `agent_inference`）。
2. `paper_*` 来源若声明章节位置，但该章节不在阅读台账中 → 自动降级为 `unverified` 并记录警告。
3. **重复写入永不升级状态**；已有边再次写入只追加 provenance。
4. 升级只能通过 `kg promote`，且必须附带满足目标状态来源要求的新证据。
5. 矛盾证据不合并：`CONTRADICTS` 边与原主张并存，节点 `contested=true`。

### 3.3 Provenance 记录

`source_type, source_ref(DOI/arXiv/path/URL), location(section/page/figure/line), quote(≤500 字符), commit, extracted_at, extractor(agent|cli|user), note`。

### 3.4 Paper Card（第 3 节要求的结构化记录）

```
meta: paper_id, reading_depth(metadata|abstract|fulltext|deep), fulltext_sha
A scientific_question: problem, importance, prior_limitations, what_changed(problem_definition|model_mechanism|training_objective|data_usage|...)
B formulation: inputs, outputs, supervision, variables, assumptions[], objective, operators[], equations[{label, latex, role, depends_on}]
C innovation: items[{statement, kind(structure|objective|probabilistic|representation|inference|paradigm), novel_vs_prior, inductive_bias, why_fits, general_or_domain}]
D implementation: modules, tensor_shapes, preprocessing, sample_construction, loss_computation, train_vs_infer, hyperparameters, repo{url, commit}, code_links[{formula, path, symbol, status, note}]
E evidence: experiments[{hypothesis_tested, result, is_ablation, is_ood}], negative_results, limitations{author_acknowledged[], inferred_from_results[], agent_proposed[]}
F signature: Method Signature（见 3.5）
```

每个断言条目都必须带 `source:{type, location, quote?}`；CLI 根据来源与台账确定最终状态。

### 3.5 Method Signature（跨领域迁移的核心表示）

`source_domain, original_problem, mathematical_abstraction, core_operators[], mechanisms[], inductive_biases[],
required_assumptions[], data_structure[], supervision[], invariances[], complexity, generalization_mechanism,
failure_conditions[], potential_target_domains[], problem_structures[]`

`mechanisms`、`data_structure`、`supervision`、`problem_structures`、`required_assumptions` 通过本体与别名归一化；
未知术语自动作为新类别加入（标记 `discovered=true`，状态 `agent_inference`），实现**动态机制发现**。

## 4. 知识图谱结构

### 4.1 节点类型（可扩展）

`Paper, Author, Venue, ResearchProblem, ScientificClaim, Method, Mechanism, MathematicalOperator, InductiveBias,
Assumption, Domain, Dataset, DataProcessingStep, EvaluationProtocol, Metric, ExperimentalResult, Limitation,
FailureMode, GitHubRepository, CodeModule, MethodSignature, ProblemStructure, TransferHypothesis, ResearchIdea,
Project, LocalExperiment, Diagnosis, Topic`

### 4.2 边类型（可扩展）

`SOLVES, USES_METHOD, USES_MECHANISM, INTRODUCES_MECHANISM, EXTENDS, CONTRADICTS, SUPPORTS, EVALUATED_ON,
MEASURED_BY, HAS_LIMITATION, DEPENDS_ON_ASSUMPTION, IMPLEMENTED_BY, HAS_CODE_MODULE, SHARES_MECHANISM_WITH,
POTENTIALLY_TRANSFERS_TO, EXPLAINS_FAILURE, INSPIRES_HYPOTHESIS, CITES, VERSION_OF, AUTHORED_BY, PUBLISHED_IN,
IN_DOMAIN, HAS_SIGNATURE, INSTANCE_OF_STRUCTURE, SUBCLASS_OF, VIOLATES_ASSUMPTION, SATISFIES_ASSUMPTION,
TESTS, OBSERVED_IN, PART_OF_PROJECT, LINKS_TO`

### 4.3 三层存储

| 层 | 位置 | 内容 |
|---|---|---|
| Global KB | `$CDRI_HOME/global.sqlite`（默认 `~/.cdri`） | 论文、方法、机制、签名、通用局限；跨项目复用，**全文只解析一次** |
| Project KB | `<project>/.cdri/project.sqlite` | 项目、本地数据集、实验、诊断、项目事实（assumption 满足情况）、冻结决策 |
| Link Layer | Project KB 中 `LINKS_TO` 等边，`dst` 为 Global 节点 ID | 将本地问题连接到全局知识；跨项目共享通过 Global 中的机制节点实现 |

两库 schema 相同（`nodes / edges / provenance / aliases / ledger / fts`），`KnowledgeBase` 类提供联合查询。

### 4.4 检索方式

关键词（别名表 + LIKE）、全文（FTS5 BM25，覆盖节点文本与全文分块）、图遍历（BFS，按边类型过滤）、
机制相似（签名分面加权 Jaccard + 本体祖先扩展）、语义（可选 sentence-transformers；否则 TF-IDF 余弦，明确标注为词汇向量降级）、
跨领域迁移候选（结构相似且领域不同）。

## 5. 搜索路由策略

1. **学科识别**：`assets/disciplines.json` 中的双语词表对查询打分，可多学科。
2. **数据源选择**：生命科学 → Europe PMC、PubMed、OpenAlex、S2（Europe PMC 覆盖 PMC 全文与 bioRxiv/medRxiv 预印本）；
   CS/ML → arXiv、DBLP、S2、OpenAlex；统计/数学/物理 → arXiv、OpenAlex、Crossref；默认 → OpenAlex、Crossref、S2。
3. **四通道检索计划**（`retrieval/planner.py`）：
   - **A In-domain**：主题 + Agent 提供的变体。
   - **B Adjacent**：根据问题结构本体（`problem_structures.json`）找到共享结构的相邻领域。
   - **C Distant**：由候选机制（问题结构建议的 + Agent 指定的 + 项目知识图谱中已有的）及其使用领域生成远域查询，排除当前学科。
   - **D Contradictory**：针对核心假设与方法生成"局限/失败/数据泄漏/重新评估/反例"查询。
4. **动态时间窗**：`recent = today − window_months(默认 24)`，`core = today − 5 年`，`foundational` 无下限；均在运行时计算。
5. **引用链扩展**：OpenAlex `referenced_works` / `cites:` 过滤；S2 recommendations（相似论文）。
6. **预算（不是配额）**：Quick/Standard/Deep 设定查询数与每查询结果数的上限，不设下限。
7. **隐私闸门**：查询包含文件路径、令牌样式字符串或超长文本时拒绝发送，除非显式 `--allow-sensitive`。

每次查询写入 `runs/<run_id>/log.jsonl`：`db, lane, query, params, timestamp, status(ok|empty|rate_limited|error|skipped_no_key|offline), n_results, error`。
报告中的覆盖范围由日志计算，失败与限流会显式列出。

## 6. 跨领域迁移机制

```
Paper Card.signature ─┐                              ┌─ Project facts (assumptions 满足/违反/未知)
                      ▼                              ▼
          normalize(ontology, aliases) ──► structural matcher ──► applicability ──► transfer candidate
                                              │ 分面得分：mechanism, operator, data_structure,
                                              │ supervision, invariance, assumption, problem_structure
                                              │ + lexical similarity（对照项）
                                              ▼
                       flags: structural_bridge / lexical_only / same_domain / already_transferred
```

- 分面得分为加权 Jaccard，本体中的祖先给予部分匹配（如 `entropic-ot` 与 `optimal-transport`）。
- **lexical_only**：术语相似度高而结构得分低 → 明确警告"仅术语相似"。
- **structural_bridge**：结构得分高且领域不同 → 有跨领域研究价值的候选。
- 适用性：源方法的 `required_assumptions` 与 `failure_conditions` 对照项目事实 → `satisfied / violated / unknown`；
  违反项进入 Negative Transfer Risk；未知项生成待核查清单与检索查询。
- 已有迁移检查：知识图谱中目标领域是否已有使用同一机制的论文，并生成核查检索式。
- 输出**分面分解**而非单一结论；候选以 `TransferHypothesis`（状态 `hypothesis`）入库，`INSPIRES_HYPOTHESIS` 边记录来源，支持谱系追溯。

## 7. 自动触发规则

| 触发 | 条件（`SKILL.md` + `cdri diagnose triage` 闸门） | 行为 |
|---|---|---|
| Task-triggered | 重要研究任务开始，`cdri graph coverage --topic` 显示相关机制/论文覆盖不足 | Quick/Standard 检索 |
| Failure-triggered | 症状属于非琐碎类，且（可复现 或 尝试次数 ≥ 2），常规检查已完成 | 先代码/数据/协议检查，再针对性检索 |
| 不触发 | SyntaxError、ImportError、路径错误、键错误、形状不匹配、单次表现不佳 | 常规调试 |
| Discovery-driven | 用户明确要求调研/扩展 | Deep，四通道 |
| Incremental | 用户调用 `refresh` 或外部调度器（cron/CI）调用 `cdri refresh run` | 只检索上次检查之后的新文献 |

Skill 不在 Agent 未运行时后台工作；`refresh` 只在被调用时执行。

## 8. 存储与缓存

```
$CDRI_HOME (默认 ~/.cdri)
├── config.json                     # 非敏感配置；API Key 只从环境变量读取
├── global.sqlite                   # Global KB
└── cache/
    ├── http/<host>/<sha1>.json      # HTTP 响应缓存（TTL：检索 7 天，元数据 30 天）
    ├── fulltext/<canonical>/        # raw.(pdf|html|xml), parsed.md(含 sentinel), sections.json, meta.json
    └── repos/<owner>__<name>/       # 浅克隆（blob:none），固定 commit
<project>/.cdri
├── project.json                    # 项目画像、事实、冻结决策
├── project.sqlite                  # Project KB + Link layer
├── runs/<run_id>/{plan.json, log.jsonl, records.jsonl, screening.jsonl}
├── diagnoses/<id>.json
├── sessions/<id>.json              # 长任务进度与断点
└── exports/                        # 图与报告
```

## 9. 安全与权限边界

1. **外部内容不可信**：全文缓存首行写入不可信声明；SKILL.md 规定论文/仓库/网页中的指令不构成授权。
2. **代码分析只做静态解析**：从不执行、导入或安装被分析仓库的代码。
3. **数据不外传**：只有检索查询发送到外部 API；隐私闸门拦截疑似敏感查询；项目代码、数据、日志从不上传。
4. **合法全文**：只使用开放获取来源与用户本地提供的文件；不做付费墙绕过或浏览器登录抓取。
5. **不擅自实验**：CLI 不运行训练；`experiment record` 只记录用户/Agent 已执行的结果，且需存在的产物路径才可标为 `experiment_observed`。
6. **冻结决策**：`project.json.frozen_decisions` 在 diagnose/ideate/story 输出中显式列出；假设卡片必须声明是否触及冻结决策。
7. **可撤销**：知识写入均有时间戳与 provenance；`kg retract` 将条目标记为撤回而不删除历史。
8. **API Key**：只从环境变量读取，不写入缓存或日志；日志中的 URL 去除 key 参数。

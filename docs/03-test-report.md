# 第四阶段：测试报告

报告日期：2026-10-25。环境：Windows 10.0.26300，Python 3.9.13（Anaconda），pytest 7.1.2，SQLite FTS5 可用，git 可用；
可选依赖：PyMuPDF（fitz）、sentence-transformers 已安装，pymupdf4llm、pypdf 未安装。

本报告只记录**实际执行过**的测试与结果。未执行的项目在第 4 节明确列出。

---

## 1. 离线自动化测试（unit / integration / scenario A–E / installer）

命令：`python -m pytest tests -v`。完整输出保存在 [`pytest-output.txt`](pytest-output.txt)。

**结果：53 passed，0 failed，0 skipped，约 18 秒。**

所有测试离线运行：HTTP 由 `CDRI_FIXTURES/routes.json` 路由到合成 fixture（S2 固定返回 429、dblp 无路由 → `offline`、
未知 DOI → 404），日期固定 `CDRI_TODAY=2026-06-15`，测试前清除所有 API Key 环境变量。fixture 中的论文全部是合成的
（标题带 `[SYNTHETIC FIXTURE]`，DOI 前缀 `10.5555/cdri.fx.*`，arXiv 号 `9912.00001` 处于不可能的编号区间），
代码仓库是 `tests/fixtures/repo_tfbind/` 在临时目录 `git init` 后的真实本地 commit。

| 文件 | 测试数 | 验证内容 |
|---|---|---|
| `test_unit.py` | 32 | 标识符解析与规范化；预印本 DOI 规则；证据等级上限与阅读台账闸门；不自动升级 + `promote`；CONTRADICTS → contested 与撤回；全局/项目层隔离；动态时间窗；四通道计划与基于结构的 distant 查询；隐私闸门；预印本并入正式版本去重；筛选不凑数；指标已知值；pooled vs grouped 指标差异；可比性矩阵；分组泄漏；HTML 章节与公式解析；路由（7 个参数化用例 + 显式模式优先）；签名别名归一化；`lexical_only` 标记；日志分析；TF-IDF；Mermaid 弱边虚线；配置拒绝写入密钥；HTTP fixture 状态；**反爬 HTML 页面报告为 `blocked`** |
| `test_case_a_landscape.py` | 3 | Case A 全流程（见 2.1） |
| `test_case_b_diagnose.py` | 1 | Case B 全流程（见 2.2） |
| `test_case_c_transfer.py` | 1 | Case C 全流程（见 2.3） |
| `test_case_d_story.py` | 1 | Case D 全流程（见 2.4） |
| `test_case_e_reuse.py` | 3 | Case E 跨项目复用、增量 refresh、会话续接（见 2.5） |
| `test_commands_extra.py` | 6 | `cite expand` 双向（CITES 边）与 OpenAlex 429 时的失败报告；`code locate`（未获取全文时不猜测，获取后只返回论文中声明的链接）；`code grep`（含 YAML 等非 Python 文件）；argparse 默认值与 YAML 配置超参数提取；`signature normalize`；`audit metric-info`；`audit provenance` 模板与“verified 但无证据”检测；`audit checklist`；DOT / JSON / GraphML 导出及 problem-limitation / evidence 视图；**文档与资产中引用的每条 `cdri` 命令都真实存在**（`tools/check_command_refs.py`） |
| `test_install_and_entrypoint.py` | 6 | 在隔离的用户目录（`CDRI_INSTALL_HOME`）中：`--platform all` 安装到五个约定路径 + Codex AGENTS.md 块 + Cursor 规则，再全部卸载；安装→从安装目录运行 CLI→卸载；拒绝覆盖非 CDRI 目录；AGENTS.md 块幂等写入与移除；`--purge-data` 需 `--yes`；以子进程运行 `scripts/cdri.py`（`--help`、`CDRI_OFFLINE=1` 时检索失败被如实报告为 `offline`） |

## 2. 场景测试的具体断言

### 2.1 Case A — “调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。”

- 路由为 `landscape`；时间窗由 `CDRI_TODAY` 推导（recent_from = 2024-06-15），不是写死的年份。
- 计划同时包含 in_domain / adjacent / distant / contradictory 四通道，学科路由识别出 life_science。
- 检索结果中 S2 的 429 与 dblp 的 offline 全部出现在 `failures`；`log.jsonl` 每条都有 db/query/status。
- 同一论文的 arXiv 预印本与正式版本合并为一条（`versions` 中保留 `preprint_version`），bioRxiv DOI 与 Crossref
  posted-content 被标为 `preprint`，2014 年论文不被标为 recent。
- 空白筛选理由被拒绝（exit 2）；报告包含“未完成的检索”、预印本/正式发表区分、Contradictory 节和 AGENT 占位。
- `paper verify`：存在 → `exists`；伪造 DOI → `not_found`；标题不符 → `title_mismatch`。
- 全文：解析文件以 UNTRUSTED 头开始、以 sentinel 结束；无合法 OA 的论文返回 `unavailable` 并列出所有尝试。
- 代码映射识别 model / loss / train_loop，commit 与本地仓库一致；`code show` 显示代码使用 mean pooling。
- Paper Card：未读任何章节时阅读深度降级为 abstract；只读 Methods 后写入，Results / Discussion 来源的条目为
  `unverified`；sentinel 错误时确认失败；确认后重新写入**不会自动升级**，而是进入 `kg pending`，显式 `promote` 后才变为
  `author_claim`；公式-代码不一致记为 `code_verified` 的 discrepancy；三类 limitation 分别为
  author_claim / agent_inference / hypothesis；摘要来源的创新点保持 `unverified`；论文中的提示注入句子不影响任何状态。
- 论文报告包含 Deep Method Review、discrepancy，并注明本预印本与正式发表版本的关系及“差异未核对”。

### 2.2 Case B — “某个新模型训练正常，但在未见过的测试对象上泛化很差，甚至低于简单基线。”

- 路由为 `diagnose`；`ModuleNotFoundError` 被判为 trivial，`literature_search = not_recommended`。
- 日志分析发现 plateau 与 below_simple_baseline；预测分析发现 prediction_collapse。
- 冻结决策出现在分诊结果中；本地检查未完成时文献检索为 `deferred`，候选问题类型按“先本地后文献”排序，第一位是
  implementation_bug；完成本地检查并给出尝试次数后才变为 `recommended` 并生成定向查询。
- 泄漏审计发现 TF family 跨 split（severity high）；没有支持事实的结论被拒绝；带 artifact 的结论为
  `experiment_observed`，失败机制节点位于项目层，EXPLAINS_FAILURE 边为 `agent_inference`。
- 负面实验缺少分析字段时被拒绝；没有 artifact 文件的实验记录只能是 `user_reported`。

### 2.3 Case C — “研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。”

- 路由为 `transfer`；distant 通道查询来自问题结构对应的机制（optimal transport 等），不是主题关键词。
- 结构扫描：OT 方法的结构相似度高于同领域、词面相似的聚类方法；后者被标记 `lexical_only`，不排第一。
- 适用性检查：依据项目事实得到 satisfied / violated / unknown，violated 产生负迁移风险；迁移记录状态为 `hypothesis`，
  并生成 VIOLATES_ASSUMPTION 边。
- 含单一 `score` 的构想卡被拒绝；多维度等级卡被接受且状态为 `hypothesis`；lineage 能追溯到方法、机制、领域；
  Mermaid 导出包含虚线弱边；HTML 导出包含 SVG；迁移报告包含 Negative Transfer Risk。

### 2.4 Case D — “模型性能提升有限，但我们发现了测量噪声上限、训练目标的局限和重要的机制反例。”

- 路由为 `story`；带 artifact 的噪声上限实验为 `experiment_observed`；null 结果带完整分析。
- 未经阅读台账的 author_claim 被降级；反例 CONTRADICTS 边使主张变为 contested；聚合层级不同给出警告，
  不同协议的指标判定为 Not Directly Comparable。
- story 检查：夸大版本失败，修正版本通过；综合报告生成。

### 2.5 Case E — 知识图谱跨项目复用

- 项目 2 通过 mechanism / semantic / chunk 检索找到项目 1 深读过的论文；全文缓存复用（`from_cache`，并返回已读章节）。
- 项目 1 的私有实验在项目 2 不可见；反例出现在 contradictions 中；method-driven scan 找到项目 2 的开放问题；
  覆盖与缺口分析可用。
- Refresh 增量：新论文 p7 被发现；p6 从预印本变为正式发表并写入 `status_history`；所有源都返回 429 时检查点**不前进**。
- 会话可续接（todo、状态、最近步骤）。

## 3. 真实 API 冒烟测试（2026-10-25，联网，未配置任何 API Key）

使用临时 `CDRI_HOME` / `CDRI_PROJECT`，未设置 `CDRI_FIXTURES`。以下数字是实际输出。

### 3.1 Case A 检索

命令：`landscape run "TF-DNA binding specificity prediction" --variant "unseen transcription factor generalization" --lane in_domain --intensity quick --run-id live-a`

| 源 | 结果 |
|---|---|
| OpenAlex | ok ×6 |
| Europe PMC | ok ×6 |
| PubMed | ok ×5 |
| Crossref | ok ×4 |
| arXiv | ok ×4 |
| Semantic Scholar | **rate_limited ×4**（HTTP 429，重试 3 次后放弃，无 Key） |
| dblp | **error ×4**（返回 HTTP 202 的反爬页面 “Making sure you're not a bot!”） |

- 原始记录 214 → 去重后 155；pub_status：published 100 / preprint 46 / unknown 9；recency：recent 98 / core 37 / older 20。
- 8 个失败调用全部列在 `failures` 中，报告会写入“未完成的检索”。
- 共享前缀 `10.1101` 被正确区分：`10.1101/gr.281357.125`（Genome Research）为 published，bioRxiv 条目为 preprint。

由此发现并修复的问题（修复后离线测试仍全部通过）：

1. **dblp 反爬页面被报告为 `JSONDecodeError`** → `http.get_json` 现在识别非 JSON 的 HTML 响应，报告为
   `blocked`（附 HTTP 状态码说明），并删除该缓存条目，避免反爬页面被缓存 7 天。复测：
   `search "graph neural network" --source dblp` → `status: blocked`。新增单元测试。
2. **显式 `--lane in_domain` 被 quick 强制追加 contradictory 通道覆盖** → 显式指定的通道现在优先；若未包含
   contradictory，计划 notes 中写入 “counter-evidence coverage is missing” 警告。

交付前自查中发现并修复的其他问题：

3. `cite expand` 在第一次 OpenAlex 请求失败时会因未赋值变量崩溃（而不是报告失败）→ 已修复并加测试。
4. 诊断分类资产中的检查项引用了不存在的子命令 `audit split` / `audit recompute`（Agent 照做会失败）→
   改为 `audit leakage` / `audit metric`；新增 `tools/check_command_refs.py` 与对应测试，防止文档与 CLI 再次不一致。
5. 检索计划中 contradictory 查询的数据源列表有重复项；distant 通道曾生成单词查询 “Boltzmann” → 去重，并为过短的基础
   查询补充机制名称。
6. 论文报告页眉在缺少 venue / 年份时显示 `? ·  ·`，重复写入后来源重复显示 → 改为“venue 未知 / 年份未知”并去重；
   报告现在注明预印本与正式发表版本的关系及“差异未核对”。
7. `config check` 列出了实际未使用的 networkx → 移除。
8. `code grep` 只搜索 `.py` 文件 → 扩展到常见源码与配置文件类型（加测试）。
9. 安装器测试的卸载步骤会扫描**真实**用户目录中带标记的 CDRI 副本，若开发者本机已安装会被测试删除 → 新增
   `CDRI_INSTALL_HOME` 覆盖用户目录，测试全部在临时目录中进行。

### 3.2 引用核验

| 输入 | 结果 |
|---|---|
| `10.1038/nbt.3300` + 正确标题 | `exists`，Nature Biotechnology 2015，published，title_similarity 1.0 |
| `10.1038/nbt.3300` + 错误标题 | `title_mismatch`，title_similarity 0.234 |
| `10.1038/nbt.99999999`（编造） | `not_found`（Crossref、OpenAlex 均未找到），提示“possible fabrication or typo” |
| `arXiv:1706.03762` | `exists`，“Attention Is All You Need”，标记为 preprint（arXiv 条目无 journal_ref/DOI） |
| `10.1101/2023.12.15.571942`（DeepPBS，bioRxiv） | `exists`，preprint（Crossref posted-content），`published_version_doi: 10.1038/s41592-024-02372-w` |

注：`10.1101/2020.12.08.416800` 是测试时凭记忆构造的 DOI，返回 `not_found`；无法确认其是否真实存在，因此不作为
bioRxiv 检测的证据，改用检索结果中的真实 DOI（DeepPBS）验证。

观察到的局限：仅凭 arXiv 核验时，已在会议发表的论文（如 1706.03762 发表于 NeurIPS 2017）仍显示为 preprint，因为
arXiv 元数据没有 journal_ref。检索流程中与 OpenAlex/dblp 记录去重合并时可以得到正式版本；单独 `verify arXiv:` 时不会。

### 3.3 全文与代码

- `paper fetch arXiv:1706.03762 --plan`：arXiv HTML 第一步成功；42,056 字符，393 行，31 个章节（abstract / introduction /
  methods / results / discussion / references），sentinel 生成，发现代码链接 `github.com/tensorflow/tensor2tensor`。
- `code locate paper:arxiv:1706.03762`：返回该候选链接，并提示需确认官方仓库与对应 commit（未自动断言官方性）。
- 同一论文的 PDF（2,215,244 字节，经 `--file` 提供）由 PyMuPDF 解析：1,088 行但只识别出 7 个章节，未识别出 Methods
  （论文使用 “Model Architecture” 作为标题），未提取到代码链接；CLI 给出两条警告（缺少 methods 章节、无版面模型时公式/表格
  可能错乱）。说明 HTML 路径质量明显优于 PDF 路径。

### 3.4 未做的真实测试

- 未用真实 API 跑 adjacent / distant 通道的完整检索（离线测试覆盖了计划与执行逻辑）。
- 未测试 Unpaywall / OpenAlex OA / Europe PMC 全文 XML 的真实下载（未配置联系邮箱；离线 fixture 覆盖了解析逻辑）。
- 未测试 GitHub API 真实调用、`refresh run` 的真实增量、`CDRI_EMBEDDINGS=1` 的嵌入检索（需下载模型）。
- 未在 Claude Code / Codex CLI / Cursor / OpenCode 中端到端验证 Skill 被自动发现和调用；只验证了安装器把文件放到约定
  目录、并能从安装目录运行 CLI。各工具的发现路径可能随版本变化（可用 `--dest`）。
- 安装器只在 Windows 上测试过；macOS / Linux 的 symlink 与路径逻辑未实测。

## 4. 已实现 / 未实现清单

### 4.1 已实现（每一项都有离线测试覆盖；第 3 节列出的部分另有真实 API 验证）

- 10 种模式 + 自然语言路由，显式模式优先（`route`）。
- 多源检索：OpenAlex、Crossref、Semantic Scholar、arXiv、PubMed、Europe PMC（含 bioRxiv/medRxiv 预印本过滤）、dblp；
  学科路由；四通道计划；动态时间窗；预算上限；隐私闸门；失败逐条记录；版本合并与发表状态（含 status_history）。
- 筛选分级（建议 + 必须带理由的决定）、引用扩展（`cite expand`）。
- 引用核验（Crossref → OpenAlex → arXiv；bioRxiv 正式版本查询）。
- 合法 OA 全文级联（本地文件 → arXiv HTML/PDF → Europe PMC XML → OpenAlex OA → Unpaywall），HTML/XML/PDF 解析，
  章节识别，UNTRUSTED 头，read plan + sentinel，章节阅读台账，FTS5 段落检索。
- Paper Card 模板、校验、写入（阅读台账闸门、来源类型上限、不自动升级）。
- 代码定位（论文链接）、Python 仓库 AST 角色分类、argparse 默认值、行号与 commit 固定、`code show/grep`。
- 机制本体、问题结构、方法签名、结构 vs 词面匹配、适用性检查、负迁移风险、先前迁移检索、迁移假设记录。
- 诊断：日志 / 预测分析、分诊分类、先本地后文献、工作表、结论证据要求、冻结决策；实验记录与负面结果分析。
- 审计：分组/重复泄漏、指标重算与 pooled/grouped 对比、可比性矩阵、来源核查、检查清单。
- 知识图谱：全局/项目双层、证据等级、来源链、contested、撤回、pending/promote、五种视图、lineage、覆盖与缺口、
  导出 Mermaid / DOT / JSON / GraphML / 自包含 HTML。
- 构想卡（拒绝单一分数）、故事骨架与检查、四类报告（landscape / paper / synthesis / transfer）、refresh、会话。
- 安装 / 卸载 / 状态（四平台、用户/项目级、复制/链接、AGENTS.md 块、Cursor 规则、数据保留）。

### 4.2 部分实现 / 有局限

- **语义检索**：默认 TF-IDF（标准库）；嵌入检索代码已写但本次未实测。
- **PDF 解析**：PyMuPDF / pypdf / pdftotext 文本提取，无版面模型；章节与公式识别弱（会警告）。pymupdf4llm 路径未在本机测试。
- **公式-代码对照**：CLI 负责定位代码、固定 commit、校验与存储；“哪个公式对应哪段代码”由 Agent 阅读后填写。
- **代码角色识别**：只对 Python 做 AST 分析，基于命名与调用的启发式；其他语言（R、Julia、C++/CUDA、JS 等）只有
  文件清单、`code grep` 与 YAML/JSON/TOML 配置超参数提取，没有角色分类。
- **路由、学科识别、问题结构匹配**：关键词与规则启发式，输出是建议，需 Agent 复核。
- **报告**：CLI 生成有证据支撑的结构化部分；分析性段落（`<!-- AGENT -->`）由 Agent 填写，CLI 不生成观点。
- **dblp**：当前对脚本请求返回反爬页面，实际不可用（报告为 `blocked`）。
- **Semantic Scholar**：无 Key 时基本被限流。
- **arXiv-only 核验**：无法得知会议发表状态（见 3.2）。

### 4.3 未实现（有意不做或超出范围）

- **后台/定时运行**：Skill 只在 Agent 调用时运行；`refresh` 需显式触发，可由用户自行接入外部定时任务。
- 付费墙内容、出版商网页抓取、机构代理登录、浏览器自动化获取全文。
- Google Scholar（无官方 API）。
- bioRxiv 原生关键词检索（官方 API 不支持；通过 Europe PMC 预印本过滤代替）。
- GROBID / Nougat 等版面模型集成；图表内容理解。
- 自动运行训练、修改用户实验基线或模型权重（按规则禁止）。
- 图分析库（NetworkX 未使用；图遍历为自写 BFS）。
- 多用户共享 / 远程知识库同步。

## 5. 复现

```bash
python -m pytest tests -v              # 离线全量
python tools/run_demo.py               # 重新生成 docs/04-usage-demo.md
# 真实冒烟（需联网；会写入临时目录）
set CDRI_HOME=%TEMP%\cdri_live & set CDRI_PROJECT=%TEMP%\cdri_live_proj
python skills/cdri/scripts/cdri.py landscape run "TF-DNA binding specificity prediction" --lane in_domain --intensity quick
python skills/cdri/scripts/cdri.py paper verify 10.1038/nbt.3300
python skills/cdri/scripts/cdri.py paper fetch arXiv:1706.03762 --plan
```

# CDRI 使用演示（离线合成数据实跑）

> 本文件由 `python tools/run_demo.py` 自动生成：每个代码块都是所示命令的**真实输出**（过长处截断）。
> 数据来自 `tests/fixture_builder.py` 的**合成 fixture**（标题带 `[SYNTHETIC FIXTURE]`，DOI 前缀 `10.5555/cdri.fx.*`），不是真实文献；HTTP 由 `CDRI_FIXTURES` 路由，日期固定为 2026-06-15。
> `$CDRI` = `python <skill>/scripts/cdri.py`。在 Agent 中，这些命令由 Agent 依据 SKILL.md 调用，报告中的 `<!-- AGENT: ... -->` 段落由 Agent 在读过全文后填写。

## Case A：landscape + paper（TF–DNA binding, unseen TF generalization）

### 1. 路由：自然语言 → 模式

```text
$CDRI route "调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。"
# exit code 0
{
  "mode": "landscape",
  "explicit": false,
  "secondary": [],
  "intensity": "standard",
  "reasons": [
    "landscape: ['调研', '最新']"
  ],
  "commands": [
    "cdri landscape plan \"<topic>\" --abstraction \"<abstract problem>\"",
    "cdri landscape run --plan <plan.json> | cdri landscape run \"<topic>\"",
    "cdri screen suggest --run <id>",
    "cdri report landscape --run <id>"
  ]
}
```

### 2. 初始化项目

```text
$CDRI project init --name tfbind-unseen --goal "unseen-TF generalization"
# exit code 0
{
  "name": "tfbind-unseen",
  "goal": "unseen-TF generalization",
  "frozen_decisions": [],
  "facts": {},
  "problem_signature": null
}
```

### 3. 四通道检索计划（时间窗由当前日期动态推导）

```text
$CDRI landscape plan "TF-DNA binding specificity prediction for unseen transcription factors" --variant "zero-shot transcription factor binding prediction" --abstraction "predict interactions between sequences and unseen entities described by descriptors" --structure unseen-entity-interaction --out $TMP/plan.json
# exit code 0
{
  "written": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\plan.json",
  "queries": 16,
  "structures": [
    {
      "id": "unseen-entity-interaction",
... (13 more lines)
```

计划文件节选（时间窗、学科路由）与全部查询：

```text
{"windows": {"today": "2026-06-15", "recent_from": "2024-06-15", "core_from": "2021-06-15"}, "disciplines": ["life_science", "cs_ml"]}
[in_domain] TF-DNA binding specificity prediction for unseen transcription factors  -> europepmc,pubmed,openalex,semantic_scholar,crossref,arxiv,dblp  from 2021-06-15
[in_domain] zero-shot transcription factor binding prediction  -> europepmc,pubmed,openalex,semantic_scholar,crossref,arxiv,dblp  from 2021-06-15
[in_domain] TF-DNA binding specificity prediction for unseen transcription factors  -> europepmc  from 2024-06-15  preprints only
[in_domain] TF-DNA binding specificity prediction for unseen transcription factors  -> europepmc,pubmed  (no date floor)
[adjacent] predict interactions between sequences and unseen entities described by descriptors  -> arxiv,dblp,semantic_scholar,openalex,crossref  from 2021-06-15
[adjacent] generalization to unseen entities in pairwise interaction prediction  -> arxiv,dblp,semantic_scholar,openalex,crossref  from 2021-06-15
[adjacent] cold-start interaction prediction with side information  -> arxiv,dblp,semantic_scholar,openalex,crossref  from 2021-06-15
[distant] zero-shot generalization to unseen entities predict interactions between sequences  -> arxiv,dblp,semantic_scholar,openalex  from 2021-06-15
[distant] cold-start interaction prediction  -> arxiv,dblp,semantic_scholar,openalex  (no date floor)
[distant] energy-based model predict interactions between sequences  -> arxiv,openalex,crossref,dblp,semantic_scholar  from 2021-06-15
[distant] Boltzmann Energy-Based Modeling  -> arxiv,openalex,crossref  (no date floor)
[distant] biophysical model binding free energy predict interactions between sequences  -> arxiv,openalex,crossref  from 2021-06-15
[distant] thermodynamic model of molecular recognition  -> arxiv,openalex,crossref  (no date floor)
[contradictory] shortcut learning in interaction prediction benchmarks  -> europepmc,pubmed,openalex,semantic_scholar,crossref,arxiv,dblp  (no date floor)
[contradictory] data leakage similar entities train test split  -> europepmc,pubmed,openalex,semantic_scholar,crossref,arxiv,dblp  (no date floor)
[contradictory] random split overestimates generalization  -> europepmc,pubmed,openalex,semantic_scholar,crossref,arxiv,dblp  (no date floor)
```

### 4. 执行检索（S2 返回 429、dblp 无 fixture → 均如实列入 failures）

```text
$CDRI landscape run --plan $TMP/plan.json --run-id demoA
# exit code 0
{
  "by_db": {
    "europepmc": {
      "ok": 7
    },
    "pubmed": {
      "empty": 6
    },
    "openalex": {
      "ok": 14
    },
    "semantic_scholar": {
      "rate_limited": 11
    },
    "crossref": {
      "ok": 12
    },
    "arxiv": {
      "ok": 14
    },
    "dblp": {
      "offline": 11
    }
  },
  "failures": [
    {
      "db": "semantic_scholar",
      "query": "TF-DNA binding specificity prediction for unseen transcription factors",
      "status": "rate_limited",
      "error": "429 from fixture for https://api.semanticscholar.org/graph/v1/paper/search?query=TF-DNA+binding+specificity+prediction+for+unseen+transcription+factors&limit=20&fields=title%2Cyear%2Cvenue%2CpublicationVenue%2CexternalIds%2Cabstract%2CcitationCount%2CpublicationTypes%2CpublicationDate%2CopenAccessPdf%2Cauthors%2Cjournal%2Curl&publicationDateOrYear=2021-06-15%3A"
    },
    {
      "db": "dblp",
      "query": "TF-DNA binding specificity prediction for unseen transcription factors",
      "status": "offline",
      "error": "no fixture matches https://dblp.org/search/publ/api?q=TF-DNA+binding+specificity+prediction+for+unseen+transcription+factors&format=json&h=20"
    },
    {
      "db": "semantic_scholar",
      "query": "zero-shot transcription factor binding prediction",
      "status": "rate_limited",
      "error": "429 from fixture for https://api.semanticscholar.org/graph/v1/paper/search?query=zero-shot+transcription+factor+binding+prediction&limit=20&fields=title%2Cyear%2Cvenue%2CpublicationVenue%2CexternalIds%2Cabstract%2CcitationCount%2CpublicationTypes%2CpublicationDate%2CopenAccessPdf%2Cauthors%2Cjournal%2Curl&publicationDateOrYear=2021-06-15%3A"
    },
    {
      "db": "dblp",
... (125 more lines)
```

### 5. 筛选建议（不凑数）

```text
$CDRI screen suggest --run demoA --tier focused
# exit code 0
{
  "tier": "focused",
  "note": "suggestions only: read titles/abstracts and record decisions with reasons",
  "candidates": [
    {
      "id": "paper:doi:10.5555/cdri.fx.001",
      "title": "[SYNTHETIC FIXTURE] Protein language model features enable binding specificity prediction for unseen transcription factors",
      "year": 2026,
      "suggested_tier": "focused",
      "reasons": [
        "relevance=0.957",
        "recency=recent",
        "lanes=['adjacent', 'contradictory', 'distant', 'in_domain']",
        "status=published"
      ],
      "note": "suggestion only - agent must confirm with a reason"
    },
    {
      "id": "paper:doi:10.5555/cdri.fx.004",
      "title": "[SYNTHETIC FIXTURE] Homology leakage inflates reported generalization of TF binding models to unseen proteins",
... (52 more lines)
```

### 6. 筛选决定必须给理由（空理由被拒绝）

```text
$CDRI screen decide paper:doi:10.5555/cdri.fx.001 --run demoA --tier deep --reason " "
# exit code 2
{
  "error": "ValueError: a screening decision needs a reason"
}
```

### 6b. 带理由的决定

```text
$CDRI screen decide paper:doi:10.5555/cdri.fx.001 --run demoA --tier deep --reason "directly addresses unseen-TF generalization with a homology-aware split"
# exit code 0
{
  "recorded": [
    {
      "t": "2026-10-25T11:15:30",
      "id": "paper:doi:10.5555/cdri.fx.001",
      "tier": "deep",
      "reason": "directly addresses unseen-TF generalization with a homology-aware split",
      "in_run": true
    }
  ]
}
```

### 7. 引用核验：不存在的 DOI

```text
$CDRI paper verify doi:10.5555/cdri.fx.999
# exit code 0
{
  "id": "paper:doi:10.5555/cdri.fx.999",
  "verdict": "not_found",
  "checks": [
    {
      "source": "crossref",
      "found": false
    },
    {
      "source": "openalex",
      "found": false
    }
  ],
  "note": "identifier not found in registries: possible fabrication or typo"
}
```

### 8. 全文获取（合法 OA 级联 + read plan + sentinel）

```text
$CDRI paper fetch arxiv:9912.00001 --plan
# exit code 0
{
  "paper_id": "paper:arxiv:9912.00001",
  "tried": [
    {
      "step": "arxiv_html",
      "url": "https://arxiv.org/html/9912.00001",
      "outcome": "ok (html)"
    }
  ],
  "status": "ok",
  "kind": "html",
  "lines": 53,
  "sentinel": "27664d0c525a",
  "read_plan": [
    {
      "path": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\home\\cache\\fulltext\\paper_arxiv_9912.00001\\parsed.md",
      "offset": 1,
      "limit": 53
    }
  ],
  "section_kinds": [
    "abstract",
    "data_availability",
    "discussion",
    "introduction",
    "methods",
    "other",
    "references",
    "results",
    "supplementary"
  ],
  "code_links": [
    "https://github.com/cdri-fixture/tfbind-fixture"
  ],
  "warnings": []
}
```

### 8b. 没有合法 OA 全文时如实报告

```text
$CDRI paper fetch doi:10.5555/cdri.fx.004
# exit code 0
{
  "status": "unavailable",
  "tried": [
    {
      "step": "unpaywall",
      "outcome": "skipped: set UNPAYWALL_EMAIL or CDRI_MAILTO"
    }
  ],
  "reason": "no legal open-access full text found; supply a local file with `cdri paper fetch ID --file paper.pdf` or work at abstract level (and label it so)"
}
```

### 9. 通过 CLI 读 Methods 章节（写入阅读台账）

```text
$CDRI paper section arxiv:9912.00001 methods
# exit code 0
=== 2 Methods [methods] lines 17-30 page=1 ===
17: ## 2 Methods
18: 
19: ### 2.1 Model
20: 
21: Let x denote a one-hot DNA sequence of length L and let z denote the mean-pooled protein language model embedding of the DNA-binding domain. A convolutional encoder produces position features h(x). The TF descriptor is mapped by a small network to feature-wise scale and shift parameters (FiLM conditioning), which modulate h(x) before global max pooling. The predicted binding score is  $s(x, z) = w^\top \max_{l} \big(\gamma(z) \odot h_l(x) + \beta(z)\big)$  (Eq. 1). The conditioning is the only path through which the identity of the TF enters the model.
22: 
23: ### 2.2 Objective
24: 
25: Training minimizes a pairwise ranking loss over probes for each TF,  $\mathcal{L} = \sum_{t}\sum_{(i,j): y_{ti} > y_{tj}} \log\big(1 + e^{-(s(x_i,z_t) - s(x_j,z_t))}\big)$  (Eq. 2), so that only the within-TF ordering of probes is supervised. Scores are therefore not calibrated across TFs. We assume that binding preferences of homologous DNA-binding domains vary smoothly in embedding space.
26: 
27: ### 2.3 Data and splits
28: 
29: Probe intensities are rank-normalized per experiment. TFs are clustered by DNA-binding domain family at 40 percent sequence identity and whole clusters are assigned to train, validation or test, so that test TFs have no close homolog in training. Hyperparameters: learning rate 0.001, batch size 256, 30 epochs, early stopping on validation Spearman.
30: 
--- ledger: recorded (mode=cli_read) for each covered section
```

### 10. 代码-方法映射（commit 固定）

```text
$CDRI code analyze $TMP/repo
# exit code 0
{
  "repo": {
    "path": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\repo",
    "url": "",
    "commit": "dfb578237bb53e0030b48c58f6e553ab44749a2f",
    "owner": "",
    "name": "repo"
  },
  "by_role": {
    "loss": [
      "losses.py::pairwise_ranking_loss"
    ],
    "model": [
      "model.py::FiLM",
      "model.py::TFBindModel"
    ],
    "dataset": [
      "train.py::ProbeDataset"
    ],
    "evaluation": [
      "train.py::evaluate"
    ],
    "train_loop": [
      "train.py::train"
    ],
    "config_cli": [
      "train.py::main"
    ]
  }
}
```

### 11. Paper Card 写入知识库：未读章节的结论不会成为 author_claim

```text
$CDRI paper ingest $TMP/card.json
# exit code 0
{
  "paper_id": "paper:arxiv:9912.00001",
  "reading_depth": "deep",
  "write_warnings": [
    "section '1 Introduction' of paper:arxiv:9912.00001 is not in the reading ledger; downgraded to unverified",
    "section '3 Results' of paper:arxiv:9912.00001 is not in the reading ledger; downgraded to unverified",
    "section '4 Discussion and Limitations' of paper:arxiv:9912.00001 is not in the reading ledger; downgraded to unverified",
    "section 'Code availability' of paper:arxiv:9912.00001 is not in the reading ledger; downgraded to unverified"
  ]
}
```

### 12. 用 sentinel 确认已读完全文

```text
$CDRI paper confirm arxiv:9912.00001 27664d0c525a
# exit code 0
{
  "confirmed": true,
  "paper_id": "paper:arxiv:9912.00001",
  "sections": 12
}
```

### 13. 重新写入：不自动升级，进入待审队列

```text
$CDRI paper ingest $TMP/card2.json
# exit code 0
{
  "write_warnings": [
    "edge e:00d1aba0fdaa9bf5: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:234216e2e8a50615: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:2486ee22c8ab386d: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:6648b97f6b0718d7: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:8593ea156fda73e8: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:9531a7aefe446551: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:95d8cdfbb4acfc97: new evidence supports author_claim (current unverified); not upgraded automatically",
    "edge e:96cea241ba4ded17: new evidence supports author_claim (current unverified); not upgraded automatically",
    "new evidence would support author_claim (current unverified); status NOT upgraded automatically - use `cdri kg promote limitation:paper-arxiv-9912-00001-author_acknowledged-0`",
    "new evidence would support author_claim (current unverified); status NOT upgraded automatically - use `cdri kg promote problem:unseen-tf-binding-specificity`",
... (4 more lines)
```

### 14. 待审升级列表

```text
$CDRI kg pending
# exit code 0
[
  {
    "id": "problem:unseen-tf-binding-specificity",
    "current": "unverified",
    "supported": "author_claim"
  },
  {
    "id": "result:paper-arxiv-9912-00001-0",
    "current": "unverified",
    "supported": "author_claim"
  },
  {
    "id": "result:paper-arxiv-9912-00001-neg-0",
    "current": "unverified",
    "supported": "author_claim"
  },
  {
    "id": "limitation:paper-arxiv-9912-00001-author_acknowledged-0",
... (44 more lines)
```

### 15. 显式升级（需要引用已读章节）

```text
$CDRI kg promote result:paper-arxiv-9912-00001-0 --status author_claim --source-type paper_fulltext --ref paper:arxiv:9912.00001 --location "3 Results"
# exit code 0
{
  "id": "result:paper-arxiv-9912-00001-0",
  "status": "author_claim",
  "promoted": true,
  "warnings": []
}
```

### 16. Deep Method Review 报告（节选）

```text
$CDRI report paper --id arxiv:9912.00001
# exit code 0
# Deep Method Review：[SYNTHETIC FIXTURE] Protein language model features enable binding specificity prediction for unseen transcription factors

- ID：`paper:arxiv:9912.00001` · 预印本 · venue 未知 · 年份未知 · [arXiv:9912.00001](https://arxiv.org/abs/9912.00001)
- 阅读深度：**deep**（阅读台账：13 个章节记录）
- 版本关系：本条为 `paper:doi:10.5555/cdri.fx.001` 的另一版本（后者：正式发表，Fixture Journal of Computational Biology）。所读内容来自本版本；与正式版本的差异未核对。

> 证据标签：**Verified Fact**（登记处/代码/本地实验核验）· **Author Claim**（论文原文主张）· **Agent Interpretation**（Agent 推断）· **Hypothesis**（待检验假设）· **Unsupported / Unverified**。

## 方法：Fixture PLM-FiLM TF binding model

### 输入 / 输出 / 监督 / 目标

- **inputs**：one-hot DNA x and PLM embedding z of the DNA-binding domain
- **objective**：pairwise within-TF ranking loss

### 公式（含原文位置）

- Eq. 1（model，2.1 Model）：$$s(x,z)=w^T max_l(γ(z)⊙h_l(x)+β(z))$$

### 机制 Mechanism

- Conditioning on Entity Descriptors (zero-shot via side information) — **Agent Interpretation**

### 核心算子

- FiLM conditioning — **Author Claim** · 来源：paper_fulltext@2.1 Model

### 归纳偏置

- TF specificity is a smooth function of DBD embedding — **Author Claim** · 来源：paper_fulltext@2.1 Model

### 依赖假设

- binding preferences vary smoothly in DBD embedding space — **Author Claim** · 来源：paper_fulltext@2.2 Objective

### 代码映射

- model.py::TFBindModel.forward — **Verified Fact (code)** · formula=Eq. 1 · match=discrepancy  · 来源：code@model.py:25-31
- losses.py::pairwise_ranking_loss — **Verified Fact (code)** · formula=Eq. 2 · match=consistent  · 来源：code@losses.py:6-14

### Limitation

- fails for TF families absent in training — **Unsupported / Unverified** · category=author_acknowledged · 来源：paper_fulltext@4 Discussion and Limitations
- random splits overstate generalization — **Agent Interpretation** · category=inferred_from_results
- ranking loss may hide calibration failures across TFs — **Hypothesis** · category=agent_proposed
... (19 more lines)
```

## Case B：diagnose（训练正常，但未见对象泛化差、低于基线）

### 1. 常规软件错误不触发文献检索

```text
$CDRI diagnose triage "ModuleNotFoundError: No module named 'torch_scatter'"
# exit code 0
{
  "trivial": true,
  "literature_search": "not_recommended",
  "advice": "Install / fix the import path."
}
```

### 2. 训练日志分析

```text
$CDRI diagnose log $TMP/train_log.csv --metric-col val_spearman --baseline 0.35
# exit code 0
{
  "file": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\train_log.csv",
  "rows": 40,
  "columns": [
    "epoch",
    "train_loss",
    "val_loss",
    "val_spearman"
  ],
  "observations": [
    {
      "symptom": "info",
      "detail": "final val-train loss gap 0.5169"
    },
    {
      "symptom": "plateau",
      "detail": "val_spearman plateau: {'plateau': True, 'relative_gain_last_window': 0.0, 'window': 5}"
    },
    {
      "symptom": "below_simple_baseline",
      "detail": "best val_spearman=0.29 vs baseline 0.35"
    }
  ],
  "note": "observations only; map them to candidate problem types with `cdri diagnose triage`"
... (1 more lines)
```

### 3. 预测分布分析

```text
$CDRI diagnose preds $TMP/preds.csv --group-col tf
# exit code 0
{
  "file": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\preds.csv",
  "n": 60,
  "pred_std": 0.001708,
  "true_std": 0.287228,
  "std_ratio": 0.0059,
  "observations": [
    {
      "symptom": "prediction_collapse",
      "detail": "prediction std / target std = 0.006 (< 0.1): near-constant predictions"
    },
    {
      "symptom": "prediction_collapse",
      "detail": "within-tf prediction spread (0) << between-group spread (0.00171): model may predict a per-group constant"
    }
  ]
... (1 more lines)
```

### 4. 冻结决策

```text
$CDRI project freeze "keep the PLM-FiLM backbone" --reason "agreed with PI"
# exit code 0
{
  "name": "tfbind-unseen",
  "goal": "unseen-TF generalization",
  "frozen_decisions": [
    {
      "decision": "keep the PLM-FiLM backbone",
      "reason": "agreed with PI",
      "t": "2026-10-25T11:15:32"
    }
  ],
  "facts": {},
  "problem_signature": null
}
```

### 5. 分诊：先做本地检查，文献检索延后

```text
$CDRI diagnose triage "model trains normally but generalizes poorly to unseen TFs, below simple baseline" --obs $TMP/obs.json --topic "TF binding prediction"
# exit code 0
{
  "literature_search": "deferred",
  "candidate_problem_types": [
    {
      "id": "implementation_bug",
      "label": "Implementation Bug",
      "order": 1,
      "checks": [
        "Overfit a tiny batch (≤ 32 samples): loss should approach 0",
        "Compare forward outputs against a reference implementation or the paper equations on a toy input",
        "Check train/eval mode (dropout, batchnorm), detach/no_grad placement, loss reduction",
        "Verify label/feature alignment after joins and shuffles (index mismatch)",
        "Assert no NaN/Inf; check learning-rate schedule actually applied"
      ],
      "needs_literature": false
    },
    {
      "id": "data_processing_error",
      "label": "Data Processing Error",
      "order": 2,
      "checks": [
        "Re-derive preprocessing from raw data for 3 random samples by hand",
        "Check normalization fitted on train only (no test statistics leakage)",
        "Check filtering removed the same features/entities in train and test",
        "Verify identifiers (gene symbols vs Ensembl, genome build, species) are consistent",
        "Run `cdri audit leakage` for group/duplicate/spatial leakage"
      ],
      "needs_literature": false
    },
    {
      "id": "evaluation_mismatch",
      "label": "Evaluation Mismatch",
      "order": 3,
      "checks": [
        "Recompute the metric at the paper's aggregation level (`cdri audit metric --group ...`)",
        "Confirm the same split unit (entity-level vs sample-level) as the comparator",
... (81 more lines)
```

### 6. 数据泄漏审计（按 TF family 分组）

```text
$CDRI audit leakage $TMP/split.csv --split split --group tf_family
# exit code 0
{
  "file": "C:\\Users\\ROG\\AppData\\Local\\Temp\\tmpby69a0sp\\split.csv",
  "n_rows": 16,
  "splits": {
    "test": 5,
    "train": 11
  },
  "findings": [
    {
      "check": "group overlap on 'tf_family'",
      "n_groups": 4,
      "n_shared": 1,
      "examples": {
        "C2H2": [
          "test",
          "train"
        ]
      },
      "severity": "high",
      "meaning": "1 'tf_family' values appear in more than one split"
    }
  ],
... (5 more lines)
```

### 7. 负面结果必须带分析

```text
$CDRI experiment record --name "family-split retrain" --outcome negative --metrics "{"median_spearman": 0.21}"
# exit code 2
{
  "error": "ValueError: negative/null results need the negative-result analysis fields ['module_ineffective', 'problem_misformulated', 'supervision_cannot_identify', 'data_quality_limits', 'baseline_captures_signal', 'new_mechanistic_insight'] (answer 'unknown' where not known)"
}
```

## Case C：transfer（空间细胞扰动预测，跨学科方法迁移）

另一个项目目录（`--project $TMP/proj2`）；全局知识库与 Case A 共享，项目层相互隔离。

### 1. 路由

```text
$CDRI route 研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。
# exit code 0
{
  "mode": "transfer",
  "reasons": [
    "transfer: ['其他学科', '迁移']"
  ]
}
```

### 2. 新项目

```text
$CDRI --project $TMP/proj2 project init --name spatial-perturb --goal "spatial perturbation response"
# exit code 0
{
  "name": "spatial-perturb",
  "goal": "spatial perturbation response",
  "frozen_decisions": [],
  "facts": {},
  "problem_signature": null
}
```

### 3. 定义问题签名（问题结构，而非关键词）

```text
$CDRI --project $TMP/proj2 project problem $TMP/problem.json
# exit code 0
{
  "problem_id": "problem:project-spatial-perturb"
}
```

### 4. 结构匹配扫描（结构相似度 vs 词面相似度）

```text
$CDRI --project $TMP/proj2 transfer scan --min-structural 0.0
# 节选：每个候选的关键字段
{"method_id": "method:fixture-ot-cell-response", "source_domain": "single_cell_computational_biology", "structural_similarity": 0.484, "lexical_similarity": 0.0, "new_mechanisms_for_target": ["optimal-transport"], "flags": ["structural_bridge: shared structure across different domains"]}
{"method_id": "method:fixture-equivariant-particles", "source_domain": "computational_physics", "structural_similarity": 0.339, "lexical_similarity": 0.067, "new_mechanisms_for_target": ["symmetry-equivariance"], "flags": []}
{"method_id": "method:fixture-plm-film-tf-binding-model", "source_domain": "computational_biology", "structural_similarity": 0.0, "lexical_similarity": 0.048, "new_mechanisms_for_target": ["meta-learning-conditioning"], "flags": []}
{"method_id": "method:fixture-spatial-clustering", "source_domain": "spatial_transcriptomics", "structural_similarity": 0.0, "lexical_similarity": 0.538, "new_mechanisms_for_target": ["low-rank-structure"], "flags": ["lexical_only: shared vocabulary but little shared structure - do not treat as transferable", "same_domain"]}
```

### 5. 记录项目事实

```text
$CDRI --project $TMP/proj2 project fact mass-conservation-or-unbalanced-relaxation false --note "perturbation kills cells"
# exit code 0
{
  "facts": {
    "mass-conservation-or-unbalanced-relaxation": false,
    "_notes": {
      "mass-conservation-or-unbalanced-relaxation": "perturbation kills cells"
    }
  }
}
```

### 6. 适用性检查与负迁移风险

```text
$CDRI --project $TMP/proj2 transfer check method:fixture-ot-cell-response
# exit code 0
{
  "method": "method:fixture-ot-cell-response",
  "assumptions": [
    {
      "assumption": "meaningful-ground-cost",
      "origin": "method",
      "state": "unknown",
      "note": null
    },
    {
      "assumption": "comparable-supports",
      "origin": "method",
      "state": "unknown",
      "note": null
    },
    {
      "assumption": "mass-conservation-or-unbalanced-relaxation",
      "origin": "optimal-transport",
      "state": "violated",
      "note": "perturbation kills cells"
    }
  ],
  "failure_conditions": [
    {
      "failure_condition": "no-meaningful-cost",
      "origin": "optimal-transport",
      "state": "unknown"
    },
    {
      "failure_condition": "strong-mass-imbalance-without-unbalanced-ot",
      "origin": "optimal-transport",
      "state": "unknown"
    },
    {
      "failure_condition": "n-squared-memory-infeasible",
      "origin": "optimal-transport",
      "state": "unknown"
    }
  ],
  "negative_transfer_risks": [
... (20 more lines)
```

### 7. 记录迁移假设（状态 = hypothesis）

```text
$CDRI --project $TMP/proj2 transfer record method:fixture-ot-cell-response --rationale "shared unpaired-alignment structure"
# exit code 0
{
  "transfer_id": "transfer:fixture-ot-cell-response--project-spatial-perturb",
  "status": "hypothesis"
}
```

### 8. 迁移子图（Mermaid；虚线 = 弱证据）

```text
$CDRI --project $TMP/proj2 graph export --view transfer --format mermaid
# exit code 0
flowchart LR
  n0["Project: spatial-perturb<br/><small>User Reported</small>"]
  n1["ResearchProblem: predict spatially resolved cellular responses t…<br/><small>User Reported</small>"]
  n2["Paper: [SYNTHETIC FIXTURE] Protein language model feat…<br/><small>Verified Fact</small>"]
  n3["Method: Fixture PLM-FiLM TF binding model<br/><small>Unsupported / Unverified</small>"]
  n4["Mechanism: Conditioning on Entity Descriptors (zero-shot v…<br/><small>vocabulary</small>"]
  n5["Domain: computational_biology<br/><small>vocabulary</small>"]
  n6["Mechanism: Graphical Models / Message Passing<br/><small>vocabulary</small>"]
  n7["Method: fixture ot cell response<br/><small>Agent Interpretation</small>"]
  n8["Mechanism: Optimal Transport<br/><small>vocabulary</small>"]
  n9["Domain: single_cell_computational_biology<br/><small>vocabulary</small>"]
  n10["Method: fixture equivariant particles<br/><small>Agent Interpretation</small>"]
  n11["Mechanism: Symmetry / Equivariance<br/><small>vocabulary</small>"]
  n12["Domain: computational_physics<br/><small>vocabulary</small>"]
  n13["Method: fixture spatial clustering<br/><small>Agent Interpretation</small>"]
  n14["Mechanism: Low-Rank / Factorized Structure<br/><small>vocabulary</small>"]
  n15["Domain: spatial_transcriptomics<br/><small>vocabulary</small>"]
  n16["TransferHypothesis: method:fixture-ot-cell-response → problem:proje…<br/><small>Hypothesis</small>"]
  n17["Assumption: mass conservation or unbalanced relaxation<br/><small>vocabulary</small>"]
  n0 -->|LINKS_TO| n1
  n2 -->|USES_METHOD| n3
  n3 -.->|USES_MECHANISM| n4
  n3 -.->|IN_DOMAIN| n5
  n1 -->|USES_MECHANISM| n6
  n7 -.->|USES_MECHANISM| n8
  n7 -.->|IN_DOMAIN| n9
  n10 -.->|USES_MECHANISM| n11
  n10 -.->|USES_MECHANISM| n6
  n10 -.->|IN_DOMAIN| n12
  n13 -.->|USES_MECHANISM| n14
  n13 -.->|IN_DOMAIN| n15
  n7 -.->|POTENTIALLY_TRANSFERS_TO| n1
  n7 -.->|INSPIRES_HYPOTHESIS| n16
  n8 -.->|INSPIRES_HYPOTHESIS| n16
  n1 -->|VIOLATES_ASSUMPTION| n17
  classDef assumption fill:#76b7b2,color:#111;
  class n17 assumption;
  classDef domain fill:#86bcb6,color:#111;
  class n5,n9,n12,n15 domain;
  classDef mechanism fill:#e15759,color:#111;
... (12 more lines)
```

### 9. 来源追溯

```text
$CDRI --project $TMP/proj2 graph lineage transfer:fixture-ot-cell-response--project-spatial-perturb
# exit code 0
{
  "root": "transfer:fixture-ot-cell-response--project-spatial-perturb",
  "derived_from": [
    {
      "src": "method:fixture-ot-cell-response",
      "type": "INSPIRES_HYPOTHESIS",
      "dst": "transfer:fixture-ot-cell-response--project-spatial-perturb",
      "status": "Hypothesis"
    },
    {
      "src": "mechanism:optimal-transport",
      "type": "INSPIRES_HYPOTHESIS",
      "dst": "transfer:fixture-ot-cell-response--project-spatial-perturb",
      "status": "Hypothesis"
    },
    {
      "src": "method:fixture-ot-cell-response",
      "type": "USES_MECHANISM",
      "dst": "mechanism:optimal-transport",
      "status": "Agent Interpretation"
    },
    {
      "src": "method:fixture-ot-cell-response",
      "type": "IN_DOMAIN",
... (27 more lines)
```

### 10. 项目隔离：Case A 项目的冻结决策在此不可见

```text
$CDRI --project $TMP/proj2 project show
# exit code 0
{
  "name": "spatial-perturb",
  "frozen_decisions": []
}
```

## 会话续接

### 开始会话

```text
$CDRI session start landscape "TF binding unseen generalization"
# exit code 0
{
  "id": "20261025-111533-landscape-tf-binding-unseen-generalizati",
  "mode": "landscape",
  "goal": "TF binding unseen generalization",
  "intensity": "standard",
  "started": "2026-10-25T11:15:33",
  "status": "open",
  "steps": [],
  "state": {},
  "todo": []
}
```

### 记录待办

```text
$CDRI session todo "read Results of fx.004 critique"
# exit code 0
{
  "id": "20261025-111533-landscape-tf-binding-unseen-generalizati",
  "mode": "landscape",
  "goal": "TF binding unseen generalization",
  "intensity": "standard",
  "started": "2026-10-25T11:15:33",
  "status": "open",
  "steps": [],
  "state": {},
  "todo": [
    {
      "text": "read Results of fx.004 critique",
      "done": false
    }
  ]
}
```

### 续接摘要

```text
$CDRI session resume
# exit code 0
{
  "id": "20261025-111533-landscape-tf-binding-unseen-generalizati",
  "mode": "landscape",
  "goal": "TF binding unseen generalization",
  "intensity": "standard",
  "state": {},
  "open_todo": [
    "read Results of fx.004 critique"
  ],
  "last_steps": []
}
```


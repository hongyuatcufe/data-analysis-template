---
name: data-analysis-pipeline
description: >-
  Engineering-grade data analysis pipeline for research, surveys, and policy evaluation. Use when
  reproducible, audit-ready analysis is required: staged ordering, methodological transparency,
  mandatory cleaning documentation, and independent audit before report delivery.
version: 1.1.1
author: hongyuatcufe
tags: [data-analysis, research, survey, statistics, reproducibility, audit, likert, cross-period]
agents: [claude-code, codex, cursor, gemini-cli, cline, windsurf, copilot]
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Data Analysis Pipeline — 工程级数据分析流水线

## 何时使用本 skill

适用：
- 问卷调查、田野调查、行政数据分析，输出物要作为正式报告/论文/政策建议
- 跨期对比（年度、季度、阶段）分析，需明确可比性
- 实验/对照评估，需独立复查与方法学约束
- 任何要求**可重现、可追溯、可审计**的研究级工作

**不适合**（应改用其他 skill）：
- 对话式即兴数据问答（"帮我看看销售趋势"）→ 用 `data-analysis`
- 一次性 SQL 切片或 dashboard 调试 → 用 `data-analysis` 或 `looker-studio-bigquery`
- 代码模式扫描 → 用 `pattern-detection`

## 核心理念

研究级数据分析与即兴分析的区别在于**纪律**：
1. **流水线强制顺序** —— 01 清洗 → 02 描述 → 03 交叉 → 04 对比 → 05 可视化 → 最终审计复查（`99_audit`） → 报告
2. **方法学透明** —— 每个统计方法的选择必须有书面理由（分析目的、变量类型、样本量、分布、领域惯例），不存在"默认就这么用"
3. **独立复查不可跳过** —— 最终审计复查（`99_audit`）所有项目必须通过才允许出报告
4. **可重现** —— 所有操作代码驱动，禁止手工修改中间文件
5. **方法论文档随交付** —— 清洗规则、分析方法、可比性说明必须随报告一起

绝不在没有数据探查的情况下直接出结论；绝不在没有复查的情况下发布报告。

---

## 子命令（按需调用）

### `init` —— 初始化项目骨架

执行步骤：
1. 检查 `uv` 是否可用；缺失则提示用户先安装 `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. 创建标准目录：
   ```
   data/        # raw/、cleaned/、配置 JSON、方法论 md
   scripts/     # 01_~99_ 编号 Python 脚本
   output/
     tables/    # Excel 统计表
     charts/    # HTML 交互图 + PNG 300DPI
   report/      # 最终 Markdown/Word/PPT
   ```
3. 写入 `pyproject.toml`（参考本 skill 的 `templates/pyproject.toml.template`）
4. 复制本 skill 的 `templates/CLAUDE.md` 到项目根（Codex 用户改名为 `AGENTS.md`、Cursor 用户改为 `.cursor/rules/research.mdc`）
5. 复制本 skill 的 `templates/utils_template.py` 为项目 `scripts/utils.py`
6. 生成空脚本 `01_clean.py` `02_describe.py` `03_cross.py` `04_compare.py` `05_viz.py` `99_audit.py`，每个含 docstring 说明阶段产出
7. 执行 `uv sync`

---

### `explore` —— 数据探查（必须先做）

按官方 data-analysis skill 的 Data Overview 模板输出：

```markdown
## Dataset Overview

**Source**: <file>
**Rows**: N
**Columns**: K
**Time Range**: <start> to <end>（若有时间列）

### Column Summary
| Column | Type | Non-null % | Unique | Sample Values |
|--------|------|-----------|--------|---------------|
| ...    | ...  | ...       | ...    | ...           |

### Data Quality Issues
- [N] rows with missing values in [column]
- [Y] potential duplicates
- [Z] out-of-range values
- 候选清洗规则建议清单
```

代码模式（utils.py 已提供）：
```python
from utils import data_quality_report
report = data_quality_report(df)
report.to_excel("output/tables/00_data_quality.xlsx")
```

---

### `clean` —— 数据清洗

**强制要求**：
1. 列出候选清洗规则供用户确认（不擅自删除）：
   - 完全重复行
   - 直线作答（矩阵题全部子项同一答案）—— 仅适用于包含反向题或长度大于 5 且无反向题的矩阵，以防误伤合理的一致性态度答卷。
   - 正反向题逻辑矛盾（A != 非A）—— 基于先验的问卷 schema（如 `data/config/questionnaire_schema.json` 中的 `positive` 和 `negative` 分组）进行确定性逻辑矛盾检测（例如同一题组中正向和反向陈述全部选高分，逻辑上自相矛盾）。
   - 数值范围异常（如年龄<0 或 >120）
   - 关键字段缺失
2. 实施确认的规则
3. **三个必须输出**：
   - `output/tables/00_cleaning_log.xlsx`（规则名/删除数/剩余 N/被删序号）
   - `data/cleaned/<name>.csv`
   - `data/cleaning_rules.md`（每条规则的判断标准、删除数、理由）

**通用清洗工具**（utils.py 提供）：
- `detect_duplicates(df, subset=None)`
- `detect_straight_line(df, matrix_groups: dict)` —— 矩阵题直线作答。**注意**：在清洗脚本中，只传入在 Schema 中定义了反向题或长度大于 5 项需要进行直线检测的矩阵列组，不可对所有矩阵无脑运行。
- `detect_contradiction(df, positive_cols, negative_cols, threshold=4)` —— 正反向矛盾判定（判定 $A \neq \text{非A}$）。
- `detect_outliers(df, col, method='iqr'|'zscore'|'range')`

清洗代码必须幂等：重复执行结果相同；中间文件可重建。

---

### `describe` —— 描述统计

按变量类型**强制选择方法**：

| 类型 | 方法 | 输出 |
|------|------|------|
| 单选/分类 | 频数 + 百分比（分母 = 有效样本）| n, % |
| 多选 | 勾选率（分母 = 总样本）| n, % |
| 有序量表（Likert） | 均值 + SD + 频数分布 | mean, SD, 1-5 分布 |
| 连续 | 5 数概括 + 均值 SD | min, Q1, median, Q3, max, mean, SD |
| 文本 | 作答率 + 字数统计 | response_rate, mean_len, median_len, max_len |

**输出**：`output/tables/01_descriptive_<panel>.xlsx`，每个变量/板块一个 Sheet。

**统计模板**（嵌入 Excel）：
```markdown
## [Variable Name]
- **n** (valid): X
- **Distribution / Mean ± SD**: ...
- **Key Findings**: <1-2 lines>
```

工具函数（utils.py）：`freq_table`, `multi_count`, `likert_stats`, `text_stats`

---

### `cross` —— 组间差异、关联与模型分析（方法选择需有依据）

先判断分析目的，再选方法。不要只根据变量类型机械套检验。

| 分析目的 | 典型问题 | 方法重点 |
|----------|----------|----------|
| 描述现状 | 现状分布如何？ | 频数、百分比、均值/中位数、置信区间 |
| 组间差异 | 不同地区/层级是否不同？ | 显著性检验 + 效应量 + 事后比较 |
| 变量关联 | 能力与需求是否相关？ | 相关、列联分析、效应量 |
| 解释/预测 | 控制其他变量后是否仍成立？ | 回归模型、稳健性/敏感性分析 |

**方法选择参考矩阵**（不是教条，需结合研究情境）：

| 自变量 × 因变量 | 默认倾向 | 何时改换 |
|---------------|---------|---------|
| 分类 × 分类 | Chi-square + Cramer's V | 2x2 且期望频数不足可用 Fisher's exact；更大 RxC 表用 Monte Carlo/置换检验，或不报告显著性 |
| 有序量表 × 分类 (k>2) | **看情境选**：①单题 Likert / 小样本 / 分布偏斜 → Kruskal-Wallis；②多题复合分数 / n≥30 每组 / 分布近对称 → ANOVA 可用 | 拿不准时双跑对照，看结论是否一致 |
| 有序量表 × 分类 (k=2) | 同上：单题 / 小样本 → Mann-Whitney；复合分数 / 大样本 → t-test | |
| 有序 × 有序 | 单题 → Spearman；复合分数 → Pearson 也可 | 看散点图判断线性 |
| 连续 × 分类 (k>2) | 先 Shapiro/Levene；满足 → ANOVA，否则 → Kruskal-Wallis | |
| 连续 × 连续 | Pearson + 散点图先看分布 | 强非线性 → Spearman 或回归 |

**效应量强制要求**：

| 方法 | 必报效应量 |
|------|------------|
| Chi-square | Cramer's V |
| t-test | Cohen's d；小样本优先 Hedges g |
| ANOVA | eta squared 或 omega squared |
| Mann-Whitney | rank-biserial correlation |
| Kruskal-Wallis | epsilon squared |
| Pearson/Spearman | r/rho 本身，建议给置信区间 |
| Logistic/ordinal 回归 | OR 或边际效应 + 置信区间 |
| 线性回归 | beta、标准化 beta（可选）、R²/调整 R² |

显著性检验必须同时报告效应量。p 值回答“是否可能非随机”，效应量回答“差异/关联有多大”。

**置信区间建议**：
- 比例：Wilson CI
- 均值：t CI；偏态/小样本可用 bootstrap CI
- 两组均值差/中位数差/效应量：bootstrap CI
- 相关系数：Pearson 用 Fisher z CI；Spearman 可 bootstrap
- 回归系数/OR：模型置信区间

**Likert 的方法学争议**：
- "Likert 是有序变量，必须用非参数" —— 经典统计学派
- "复合分数 + 大样本 → 中心极限定理使 ANOVA robust" —— 心理测量学界主流实践
- **本流水线立场**：不站队，要求**在 `data/method.md` 中说明本研究的选择理由**（量表类型、样本量、分布形态、领域惯例）

**Likert 细化规则**：
- 单个 Likert 项：报告完整分布 + 中位数/IQR + 均值/SD；推断优先 Mann-Whitney/Kruskal-Wallis
- 多题合成量表：先说明理论构念；计算 Cronbach's alpha（必要时 McDonald's omega）后再合成
- 复合分数：可用均值/SD；组间差异可用 t-test/ANOVA，但需报告分布检查与非参数稳健性
- 不要仅因题项都为 1-5 分就强行合成量表；必须同构念且信度可接受

**多重比较控制**：
- 事前指定少量核心假设：可不机械校正，但必须说明
- 探索性多题、多组检验：使用 Benjamini-Hochberg FDR
- 少量成对比较：使用 Holm-Bonferroni
- ANOVA/Kruskal-Wallis 显著后再做 post-hoc；post-hoc 需说明校正方法

**缺失值与权重**：
- 每个关键变量报告缺失率；说明分母是总样本、有效样本还是加权样本
- 缺失较低：listwise/pairwise deletion 可接受，但要说明
- 关键变量缺失较高：做敏感性分析；不得默认均值填补
- 如样本设计有权重，必须做加权统计；样本结构与总体差异明显时，至少给未加权 + 加权敏感性结果

**模型层方法**：
- 二分类结果：logistic regression
- 多分类结果：multinomial logistic regression
- 有序结果：ordinal logistic regression
- 连续/复合分数：linear regression
- 计数结果：Poisson 或 negative binomial
- 分层/嵌套数据：mixed-effects model 或聚类稳健标准误

回归模型不是“高级装饰”。只有当研究问题需要控制混杂因素、解释影响因素或预测时才使用。

**强制要求**：
1. 方法选择写进 `data/method.md`，含一句决策依据
2. 每个显著性检验同时给出效应量；关键结论建议给置信区间
3. 边界情况（如 n=20-30、分布略偏）建议双跑参数+非参数对照
4. 显著性结论严重依赖方法时（一个 p<0.05、另一个 p>0.10），必须报告两者并讨论
5. 多重检验、权重、缺失处理、异常值处理均需在方法说明中写明

**输出**：每对变量一个 Sheet，含「频数表 / 行% / 列% / 检验统计量 / p 值 / 效应量 / 置信区间（关键结论） / 所用方法 / 结论」。

工具函数：`crosstab_chi2`, `kruskal_test`, `mannwhitney_test`, `spearman_corr`, `cramers_v`, `cohens_d`, `eta_squared_anova`, `wilson_ci`, `bootstrap_ci`（参数检验用 `scipy.stats.f_oneway` / `pearsonr` / `ttest_ind`）

---

### `compare` —— 跨期/外部对比

**可比性三档分级**（强制标注）：
- ✅ **完全可比**：题目、口径、定义、分母完全一致
- ⚠️ **口径有差异**：方向可参考，数值不可直接比
- ❌ **不可比**：仅供背景参考，不进入正式对比表

**输出**：
- `output/tables/04_comparison.xlsx`（含可比性列）
- `data/comparison_notes.md`（每个指标的外部数据出处，含原文行号/页码引用）
- 加权估算时必须显示公式与权重

模板：
```markdown
## 指标：<name>
- 外部值（来源 X，年份 Y）：A
- 本期值：B
- 变化：±C（百分点 / %）
- 可比性：✅/⚠️/❌
- 说明：<问法差异、口径变化>
```

---

### `viz` —— 可视化

**图表选择矩阵**：

| 数据类型 / 目的 | 推荐图 | 工具 |
|---------------|--------|------|
| 时间趋势 | 折线 | Plotly |
| 单变量构成 | 饼/环形 | Plotly |
| 类别比较 | 并排柱 / 分组柱 | Plotly |
| 分布 | 直方图 / 箱线 | Plotly |
| 相关 | 散点 / 热力图 | Plotly |
| 多维度量表 | 雷达图 | Plotly |
| 地理 | choropleth | Plotly |
| 能力-需求 / 缺口 | 双柱 + 差值条 | Plotly |
| 跨期对比 | 双线 / 并排柱 + 变化条 | Plotly |

**强制要求**：
- 每张图必须**双输出**：`*.html`（交互）+ `*.png`（300 DPI，嵌入报告）
- 配色使用模版定义的主色系（主 `#2563eb`、强调 `#f59e0b`、正面 `#10b981`）
- 中文字体优先 `PingFang SC`、`Microsoft YaHei`
- 文件名规则：`{编号}_{主题}_{类型}.html`
- 复杂图必须有标题、图例、坐标轴标签、数据点标注

工具：`apply_plotly_theme()`, `export_html_png()`；具体图表函数在项目脚本中按数据结构实现。

---

### `audit` —— 独立复查 ⚠️ 不可跳过

这是与对话式 data-analysis 最大的区别。**未通过 audit 不允许进入 report。**

**默认 12-15 项检查清单**：

| # | 类别 | 检查项 | 验证方法 |
|---|-----|-------|---------|
| 1 | 清洗 | 每条规则删除数 | 独立重算规则逻辑 |
| 2 | 清洗 | 被删记录人工抽查 (n≥10) | 读取原始记录核对 |
| 3 | 清洗 | 关键分类变量构造 | 抽样对照原始字段 |
| 4 | 描述 | 关键单选题频数 | 独立 value_counts 对账 |
| 5 | 描述 | 关键多选题勾选率 | 独立计算（分母核对） |
| 6 | 描述 | 关键 Likert 均值 | 独立 mean 对账（差 <0.01） |
| 7 | 交叉 | 关键检验统计量独立重算 | 用 scipy（chi2_contingency / kruskal / f_oneway / spearmanr / pearsonr / ttest 等，依实际所选方法）重算 |
| 8 | 交叉 | **方法选择理由是否文档化** | 检查 `data/method.md` 中是否对每个推断检验写明选择依据 |
| 9 | 交叉 | 交叉表频数 | 抽样 cell 对账 |
| 10 | 对比 | 外部数据出处 | 查原报告/数据库引用 |
| 11 | 对比 | 本期值独立重算 | 差 <0.1pp |
| 12 | 对比 | 加权公式 | 公式独立核验 |
| 13 | 可视化 | 图表数据抽查 | Plotly data 与统计表对账 |
| 14 | 报告 | 报告关键数字 | 与统计表 cell 对账 |

**输出**：`output/tables/99_audit_report.xlsx`
- 每项标 ✅通过 / ❌失败 / ⚠️警告
- 失败必须列出差异与排查建议

**通过门槛**：所有 ❌ 必须解决；⚠️ 必须用户明确确认。

---

### `report` —— 报告生成

执行前先检查 `99_audit_report.xlsx`：有 ❌ 则**阻止**并要求先修复。

**生成流程**：
1. Markdown 主报告（每个数字标注来源 cell ID 或图表 ID）
2. Word（python-docx，嵌入 PNG）
3. PPT（python-pptx，可选）
4. **必附三个方法论附件**：
   - 附件 1：`data/cleaning_rules.md`
   - 附件 2：`data/method.md`（方法学说明）
   - 附件 3：`data/comparison_notes.md`（如有跨期对比）

---

## 通用工作流模板

### 问卷调查项目
```
init → explore → clean (直线+正反向) → describe (含 Likert)
     → cross (单题量表多倾向 K-W；复合分数可用 ANOVA，写明依据) → compare (跨期) → viz (雷达+缺口)
     → audit (14 项) → report (含 3 附件)
```

### 销售/业务数据项目
```
init → explore → clean (重复+范围) → describe (连续+分类)
     → cross (卡方+ANOVA) → viz (折线+饼) → audit (10 项) → report
```

### 实验/对照评估
```
init → explore → clean → describe (分组)
     → cross (T-test / Mann-Whitney) → compare (组间)
     → viz → audit → report
```

---

## 最佳实践

- **清洗优先**：处理缺失、重复、异常前不开始任何分析
- **指标定义明确**：测什么、怎么测、口径如何、分母是什么
- **考虑上下文**：行业基准、季节性、政策变化
- **交叉验证**：与其他数据源对账
- **保留原始数据只读**：`data/raw/` 永不修改

---

## 限制

- 运行代码应通过脚本和 `uv run` 调用；避免手工修改中间文件
- 大数据集（>100 万行）需要先采样或分块；本流水线偏分析而非工程
- 复杂模型（混合效应、SEM、贝叶斯分层）需要专门工具（lme4、PyMC 等）
- 实时数据需要单独的连接层
- 因果推断需要明确的识别策略；本 skill 不保证因果有效性
- OCR / 手写数据的字段值不保证准确性

---

## 与其他 skill 的关系

- `data-analysis`：对话式即兴探索；本 skill 是工程级流水线 → 两者互补，前期探索可用 data-analysis，进入正式分析切换本 skill
- `simplify`：分析代码完成后用此 skill 检查复用与冗余
- `review`：报告完成后做最终评审

## 参考

- 模版与示例：本 skill 的 `templates/` 子目录
- 项目级规范：`templates/CLAUDE.md`（复制到新项目根目录；Codex 改名 `AGENTS.md`，Cursor 改名 `.cursor/rules/*.mdc`）
- 通用工具骨架：`templates/utils_template.py`
- 依赖模版：`templates/pyproject.toml.template`

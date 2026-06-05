# 数据分析项目规范

> 本文档是项目级规范，任何 agent（Claude Code / Codex / Cursor / 其他 LLM）在此项目中工作时必须遵循。
> 配套 skill：`research-pipeline`（工程级数据分析流水线）。

---

## 0. 工作纪律（不可妥协）

1. **流水线强制顺序**：01 清洗 → 02 描述 → 03 交叉 → 04 对比 → 05 可视化 → 最终审计复查（`99_audit`） → 报告。**禁止跨阶段跳跃。**
2. **独立复查不可跳过**：未通过最终审计复查（`99_audit`）所有项目，不允许生成正式报告。
3. **代码驱动**：所有数据操作通过脚本完成。**禁止手工修改 CSV / Excel 中间文件。**
4. **方法论文档随交付**：清洗规则、分析方法、对比说明三份附件随报告一起交付，缺一不可。
5. **原始数据只读**：`data/raw/` 目录任何文件不得修改，只能读取。

---

## 1. 环境

- **包管理**：`uv`（不使用 pip / poetry / conda）
- **Python 版本**：在 `.python-version` 锁定（推荐 3.12）
- **依赖锁定**：`pyproject.toml` + `uv.lock`
- **启动方式**：`uv sync && uv run python scripts/XX.py`

核心依赖：
```toml
pandas, numpy, scipy           # 数据与基础统计
statsmodels                    # 回归模型、多重比较、稳健标准误
openpyxl                       # Excel 读写
plotly, kaleido                # 交互图 + PNG 导出
matplotlib, seaborn            # 静态图（备用）
python-docx, python-pptx       # 报告生成
jieba, wordcloud               # 中文文本（如有开放题）
```

---

## 2. 目录结构

```
project/
├── CLAUDE.md                  # 本文件（项目规范）
├── pyproject.toml
├── .python-version
├── data/
│   ├── raw/                   # 原始数据（只读）
│   ├── cleaned/               # 清洗后数据
│   ├── config/                # 变量映射、题目 schema、配色（JSON）
│   ├── cleaning_rules.md      # 清洗规则文档（必须）
│   ├── method.md              # 方法学说明（必须）
│   └── comparison_notes.md    # 对比说明（如有跨期对比）
├── scripts/
│   ├── utils.py               # 共享工具：路径、配色、统计函数
│   ├── 01_clean.py
│   ├── 02_describe.py
│   ├── 03_cross.py
│   ├── 04_compare.py          # 可选
│   ├── 05_viz.py
│   └── 99_audit.py            # 不可省
├── output/
│   ├── tables/                # 所有 Excel 表
│   └── charts/                # HTML 交互 + PNG 300DPI
└── report/                    # 最终交付物
    ├── report.md
    ├── report.docx
    ├── report.pptx            # 可选
    └── 附件1-3
```

---

## 3. 统计方法选择（透明 + 可辩护）

**核心原则**：本规范**不绑定**具体方法，但要求每个推断检验的选择**写入 `data/method.md`**，含一句决策依据（分析目的、变量类型、样本量、分布、领域惯例）。

### 3.0 先判断分析目的

不要从变量类型直接跳到检验方法。先判断研究问题属于哪一类：

| 目的 | 典型问题 | 方法重点 |
|------|----------|----------|
| 描述现状 | 现状分布如何？ | 频数、百分比、均值/中位数、置信区间 |
| 组间差异 | 不同地区/层级是否不同？ | 检验 + 效应量 + 事后比较 |
| 变量关联 | 能力与需求是否相关？ | 相关、列联分析、效应量 |
| 解释/预测 | 控制其他变量后是否仍成立？ | 回归模型、稳健性/敏感性分析 |

### 3.1 描述统计按变量类型

| 类型 | 方法 | 输出列 |
|------|------|--------|
| 单选 / 名义分类 | 频数 + 百分比（分母 = 有效样本） | n, % |
| 多选 | 勾选率（分母 = **总样本**） | n, % |
| 有序量表（Likert 1-5）| 均值 + SD + 完整频数分布（兼顾两派读者） | mean, SD, 1, 2, 3, 4, 5 |
| 连续 | 5 数概括 + 均值 + SD | min, Q1, median, Q3, max, mean, SD |
| 文本（开放题） | 作答率 + 字数统计 | response_rate, mean_len, median_len, max_len |

### 3.2 推断统计的方法选择（参考矩阵，非教条）

| 自变量 × 因变量 | 默认倾向 | 何时改换 / 选择依据 |
|---------------|---------|------------------|
| 分类 × 分类 | Chi-square + Cramer's V | 2x2 且期望频数不足可用 Fisher's exact；更大 RxC 表用 Monte Carlo/置换检验，或不报告显著性 |
| 有序量表 × 分类（k>2）| ①单题 Likert / 小样本 / 偏斜 → Kruskal-Wallis<br>②多题复合分数 / n≥30 每组 / 近对称 → ANOVA 可用 | 边界情况双跑对照 |
| 有序量表 × 分类（k=2）| 同上：单题 → Mann-Whitney；复合 → t-test | |
| 有序 × 有序 | 单题 → Spearman；复合分数 → Pearson 也可 | 散点图看线性 |
| 连续 × 分类（k>2）| 先 Shapiro/Levene；满足 → ANOVA，否则 → K-W | |
| 连续 × 连续 | Pearson；强非线性 → Spearman 或回归 | 散点图先看 |

### 3.3 效应量与置信区间

显著性检验必须同时报告效应量。p 值回答“是否可能非随机”，效应量回答“差异/关联有多大”。

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

置信区间建议：
- 比例：Wilson CI
- 均值：t CI；偏态/小样本可用 bootstrap CI
- 两组均值差/中位数差/效应量：bootstrap CI
- 相关系数：Pearson 用 Fisher z CI；Spearman 可 bootstrap
- 回归系数/OR：模型置信区间

### 3.4 Likert 方法学的两派立场

- **保守派**（经典统计）：Likert 是有序变量，方差齐性 / 正态性假设不成立，应非参数
- **实用派**（心理测量学）：多题复合分数 + 大样本 + CLT，ANOVA 足够 robust
- **本规范立场**：不强制站队；要求**在 `method.md` 写明本研究采用哪一派、为什么**。审稿人和读者能看到你的判断依据，胜过盲从某派。

**决策辅助**：
- 单 5 点 Likert 题，每组 n<30，分布偏斜 → 优先非参数
- 多题量表均值/总分，每组 n≥30，分布近对称 → 参数与非参数都可，写理由
- 拿不准 → 双跑参数+非参数，若结论一致只报常规一种；若结论冲突必须两种都报告并讨论

**合成量表规则**：
- 单个 Likert 项：报告完整分布 + 中位数/IQR + 均值/SD；推断优先 Mann-Whitney/Kruskal-Wallis
- 多题合成量表：先说明理论构念；计算 Cronbach's alpha（必要时 McDonald's omega）后再合成
- 复合分数：可用均值/SD；组间差异可用 t-test/ANOVA，但需报告分布检查与非参数稳健性
- 不要仅因题项都为 1-5 分就强行合成量表；必须同构念且信度可接受

### 3.5 多重比较、缺失、权重与稳健性

多重比较：
- 事前指定少量核心假设：可不机械校正，但必须说明
- 探索性多题、多组检验：使用 Benjamini-Hochberg FDR
- 少量成对比较：使用 Holm-Bonferroni
- ANOVA/Kruskal-Wallis 显著后再做 post-hoc；post-hoc 需说明校正方法

缺失值：
- 每个关键变量报告缺失率；说明分母是总样本、有效样本还是加权样本
- 缺失较低：listwise/pairwise deletion 可接受，但要说明
- 关键变量缺失较高：做敏感性分析；不得默认均值填补

权重：
- 如样本设计有权重，必须使用加权统计
- 样本结构与总体差异明显时，至少给未加权 + 加权敏感性结果
- 层级样本量很小（如省级 n 很小）时，禁止过度解释

稳健性/敏感性分析：
- 参数 vs 非参数对照
- 含/不含异常值对照
- 缺失处理方式对照
- 加权/未加权对照
- 清洗规则放宽/收紧对照

### 3.6 模型层方法

| 结果变量 | 推荐模型 |
|----------|----------|
| 二分类 | logistic regression |
| 多分类 | multinomial logistic regression |
| 有序分类 | ordinal logistic regression |
| 连续/复合分数 | linear regression |
| 计数 | Poisson 或 negative binomial |
| 分层/嵌套数据 | mixed-effects model 或聚类稳健标准误 |

回归模型不是“高级装饰”。只有当研究问题需要控制混杂因素、解释影响因素或预测时才使用。

### 3.7 跨期对比

每个对比指标必须标注可比性：
- ✅ **完全可比**：题目、口径、定义、分母完全一致
- ⚠️ **口径有差异**：方向可参考，数值不可直接比
- ❌ **不可比**：仅供背景参考

加权估算时必须显示公式和权重。

### 3.8 报告语言规则

- 相关不写因果；回归也不自动等于因果
- 非随机样本不写总体推断过强
- p>0.05 不写“没有差异”，写“未发现统计显著差异”
- 小样本显著也要提示不稳定
- 效应量小但 p 显著，写“统计显著但实际差异有限”
- 多重检验未校正时，不写强结论

---

## 4. 数据清洗规范

### 4.1 文档化要求

`data/cleaning_rules.md` 必须包含每条规则的：
- 规则名
- 判断标准（精确条件）
- 删除数量
- 被删记录的标识（序号 / ID 清单）
- 删除理由

### 4.2 清洗日志

`output/tables/00_cleaning_log.xlsx` 必须输出：
- 原始样本量
- 每条规则的命中数（含重叠）
- 最终样本量

### 4.3 通用清洗工具与先验逻辑（utils.py）

- `detect_duplicates(df, subset=None)`
- `detect_straight_line(df, matrix_groups)` —— 矩阵题直线作答。**必须限制范围**：仅对 Schema（`data/config/questionnaire_schema.json`）中包含反向题或长度大于 5 且无反向题的矩阵运行此检测，不可对所有矩阵无脑运行。
- `detect_contradiction(df, positive_cols, negative_cols, threshold=4)` —— 正反向逻辑矛盾（$A \neq \text{非A}$）。用于检测逻辑上的对立陈述矛盾。
- `detect_outliers(df, col, method='iqr'|'zscore'|'range')`

### 4.4 缺失值处理

- 保留缺失标记列（如 `q4_missing=1`）
- 描述统计的分母明确：有效样本 vs 总样本
- 多选题缺失填 0

---

## 5. 可视化规范

### 5.1 输出双格式

每张图必须同时输出：
- `*.html` —— Plotly 交互式
- `*.png` —— 300 DPI（Kaleido 导出），嵌入 Word / PPT

### 5.2 配色（utils.py 已定义）

```python
PRIMARY    = "#2563eb"   # 主色（蓝）
SECONDARY  = "#3b82f6"   # 次色
ACCENT     = "#f59e0b"   # 强调（橙）
POSITIVE   = "#10b981"   # 正面（绿）
NEGATIVE   = "#ef4444"   # 负面（红）
NEUTRAL    = "#64748b"   # 中性（灰）
```

### 5.3 字体与样式

- 中文优先：`PingFang SC`, `Microsoft YaHei`
- 网格：`#f1f5f9`，宽度 0.8
- 图例：半透明背景 + 1px 边框
- 必须有：标题、坐标轴标签、图例（多系列时）

### 5.4 图表选择

| 数据 | 推荐图 |
|------|--------|
| 时间趋势 | 折线 |
| 构成 | 饼/环形 |
| 类别比较 | 并排柱 |
| 分布 | 直方图/箱线 |
| 相关 | 散点/热力图 |
| 多维度量表 | 雷达图 |
| 缺口/差异 | 双柱+差值条 |

### 5.5 文件命名

`{编号}_{主题}_{类型}.html`，例如 `Q18_数据共享_雷达图.html`

---

## 6. 独立复查（最终审计阶段 `99_audit`）

### 6.1 复查清单最小要求

每个项目必须设计 ≥10 项独立复查，覆盖：
- 清洗规则的删除数（独立重算）
- 被删记录抽样（n ≥ 10）人工复核
- 关键描述统计的频数对账
- ≥ 2 个推断统计的独立重算
- 跨期/外部数据出处追溯（如有对比）
- 可视化数据点抽查
- 报告关键数字与统计表对账

### 6.2 输出

`output/tables/99_audit_report.xlsx`：每项标 ✅通过 / ❌失败 / ⚠️警告，失败必须列差异。

### 6.3 通过门槛

所有 ❌ 必须解决；⚠️ 必须用户明确确认；任何 ❌ 未解决禁止生成报告。

---

## 7. 报告生成规范

### 7.1 三种格式

- `report/report.md` —— Markdown 主版本（数字标注来源）
- `report/report.docx` —— Word（嵌入 PNG）
- `report/report.pptx` —— PPT（可选）

### 7.2 数字溯源

报告中每个统计数字必须可追溯到：
- 统计表 Sheet 名 + cell 引用，或
- 图表文件名 + 数据点

### 7.3 必附三附件

- 附件 1：`data/cleaning_rules.md`
- 附件 2：`data/method.md`
- 附件 3：`data/comparison_notes.md`（如有对比）

---

## 8. 代码规范

### 8.1 utils.py 集中管理

- 路径常量（`PROJECT_ROOT`, `DATA_DIR`, `OUTPUT_DIR`, ...）
- 配色常量
- 通用统计函数（描述统计、推断检验、效应量、置信区间、多重比较校正）
- 配置加载（从 `data/config/*.json` 读取变量映射、题目 schema）

### 8.2 脚本规范

- 每个脚本独立可运行（`if __name__ == "__main__":`）
- 函数幂等：重复执行结果相同，文件覆盖不报错
- 每个阶段打印进度
- 配置外置：变量映射、题目分组、配色用 JSON，不写死

### 8.3 配置外置原则

`data/config/` 下放：
- `variable_map.json` —— 原始列名 → 短变量名 → 标签
- `questionnaire_schema.json` —— 题目类型分组（RADIO / CHECKBOX / MATRIX）
- `crosstab_pairs.json` —— 交叉分析配对清单
- `comparison_indicators.json` —— 跨期对比指标清单（如有）

---

## 9. 对 Agent 的协作约束

- **禁止**跳过最终审计复查（`99_audit`）直接生成报告
- **禁止**修改 `data/raw/` 下的任何文件
- **禁止**手工修改 `data/cleaned/`、`output/` 下的中间文件（必须通过脚本）
- **必须**在修改清洗规则时同步更新 `data/cleaning_rules.md`
- **必须**在新增可视化时输出 HTML + PNG 双格式
- **必须**在变量类型不明时询问用户而非默认按连续变量处理
- **应当**在统计检验显著但样本小（n < 30）时主动提醒可靠性问题

---

## 10. 跨 Agent 兼容性

本 CLAUDE.md 设计为 agent-agnostic：

| Agent | 使用方式 |
|-------|---------|
| Claude Code | 此文件作为项目级规范自动加载 |
| Codex | 复制本文件为 `AGENTS.md` 或 `.codex/instructions.md` |
| Cursor | 复制本文件为 `.cursorrules` |
| 其他 LLM | 作为 system prompt 的一部分注入 |

不依赖任何 agent 特定语法（无 hook、无 @-mention、无 slash 命令）。

# research-pipeline — 工程级数据分析方法论

从 `education-stat-survey-2026` 项目沉淀的数据分析工作流，遵循 [skills.sh](https://www.skills.sh/) Agent Skills 开放标准（Anthropic 提出、Vercel 推动），**一份 `SKILL.md` 跨 Claude Code / Codex CLI / Cursor / Gemini CLI / Cline / Windsurf / Copilot 通用**。

---

## 1. 这套东西是什么

**不是代码库，是方法论纪律。** 把"工程级研究分析"的隐性规则显性化、可执行化：

- **流水线强制顺序**：清洗 → 描述 → 交叉 → 对比 → 可视化 → 独立复查 → 报告
- **统计方法透明**：方法选择不绑定，但必须在 `method.md` 中写明依据（分析目的、变量类型、样本量、分布、领域惯例）；显著性检验必须配套效应量，关键指标建议给置信区间；卡方期望频数不足时必须抑制显著性结论；边界情况要求双跑参数+非参数对照
- **独立复查不可跳过**：未通过 99 阶段所有项目，禁止生成正式报告
- **可重现**：所有操作脚本化，原始数据只读，配置外置 JSON
- **方法论文档随交付**：清洗规则、分析方法、对比说明三份附件强制随报告

适合：问卷调查、政策评估、田野研究、行政数据分析、任何要求 peer review 或利益相关方审查的项目。
不适合：对话式即兴数据问答（请用 `data-analysis` skill）、一次性 SQL 切片、仪表盘调试。

---

## 2. 内容结构（符合 skills.sh 标准）

```
analysis-template/
├── README.md                              # 本文件
└── skills/
    └── research-pipeline/
        ├── SKILL.md                       # 必需：流水线 + 方法学（任何 agent 读取）
        └── templates/                     # 可选 bundled 文件
            ├── CLAUDE.md                  # 项目级规范（可改名后给 Codex/Cursor/Qoder 用）
            ├── utils_template.py          # 通用工具函数骨架
            └── pyproject.toml.template    # uv 依赖锁定
```

三层职责：
- **SKILL.md** —— 当 agent 识别到"研究级数据分析"任务时激活，提供 8 个子命令（init/explore/clean/describe/cross/compare/viz/audit/report）+ 方法学约束
- **CLAUDE.md** —— 复制到目标项目根目录，作为该项目的**长期规范**（不论用什么 agent）
- **utils_template.py + pyproject.toml.template** —— 项目骨架，`uv sync` 即可起跑

---

## 3. 挂到不同 agent

下面每节都明确告诉你：**复制什么 → 改名/放到哪 → 自动触发 or 被动参考 → 如何验证生效**。

### 3.1 Claude Code

| 项 | 操作 |
|----|------|
| Skill | `cp -r skills/research-pipeline ~/.claude/skills/`（用户级）或 `.claude/skills/`（项目级） |
| 项目规范 | `cp skills/research-pipeline/templates/CLAUDE.md <new-project>/CLAUDE.md` |
| 触发 | ✅ 自动 —— Claude Code 启动时扫描 frontmatter，按 `description` 语义匹配后激活 |
| 验证 | 在新项目里问："对一个 5 点 Likert 量表 × 三个地区做组间比较应该用什么方法？" 期望回答：**Kruskal-Wallis**，不是 ANOVA |

### 3.2 OpenAI Codex CLI

| 项 | 操作 |
|----|------|
| Skill | Codex CLI 也支持 skills.sh 标准（v0.5+），放到 `~/.codex/skills/` 或项目根 `.codex/skills/` |
| 项目规范 | `cp templates/CLAUDE.md <new-project>/AGENTS.md`（Codex 的项目级指令文件） |
| 触发 | ⚠️ 部分自动 —— Codex 读取 `AGENTS.md` 作为系统指令；SKILL.md 通过 frontmatter description 被检索 |
| 验证 | 同上 Likert 问题；另问"我可以跳过 99 阶段直接出报告吗"，期望回答：**禁止** |

### 3.3 Cursor

| 项 | 操作 |
|----|------|
| Skill | 新版 Cursor 支持 `.cursor/rules/*.mdc`，把 SKILL.md 改名为 `.cursor/rules/research-pipeline.mdc` 并在头部加 Cursor 风格的 `globs` / `alwaysApply` |
| 项目规范 | `cp templates/CLAUDE.md <new-project>/.cursor/rules/data-analysis.mdc` |
| 触发 | ⚠️ 半自动 —— 根据 `globs` 匹配文件类型时激活；推荐设 `alwaysApply: true` |
| 验证 | 在 chat 里粘贴一段 ANOVA 代码，问"这段处理 Likert 量表对吗"，期望指出方法错误 |

### 3.4 Gemini CLI / Cline / Windsurf / Copilot Chat

| 项 | 操作 |
|----|------|
| Skill | 这些工具按各自惯例读取——Gemini CLI 用 `~/.gemini/skills/`；Cline 用 `.clinerules/`；Windsurf 用 `.windsurf/rules/`；Copilot 用 `.github/copilot-instructions.md` |
| 项目规范 | 同上，复制 `templates/CLAUDE.md` 改名到对应位置 |
| 触发 | 多数工具是项目级 system prompt 注入，**被动参考**而非语义激活 |
| 验证 | 同上 Likert 问题 |

### 3.5 Qoder（字节跳动 Trae 系 IDE）

| 项 | 操作 |
|----|------|
| Skill | 截至 2026-06，Qoder 的 rules 文件路径与 skills.sh 兼容性**未官方确认**；建议先放 `.qoder/rules/research-pipeline.md`（合并 SKILL.md + CLAUDE.md 内容） |
| 触发 | 被动参考 |
| 验证 | 同上 Likert 问题 |

⚠️ **重要：除 Claude Code 外，多数 agent 不会"自动触发"独立的 SKILL.md**。它们的工作模式是把 system prompt / rules 文件作为长期上下文注入。所以在这些 agent 里，**推荐做法**是把 SKILL.md 的方法学正文**追加到 CLAUDE.md / AGENTS.md / rules 文件末尾**，作为一体化的规范文档。

```bash
# Codex / Cursor / 其他：合并成单一规范文件
cat templates/CLAUDE.md skills/research-pipeline/SKILL.md > <new-project>/AGENTS.md
```

---

## 4. 不绑定 agent 时怎么用

把以下两份拼起来作为任何 LLM 的 system prompt：

```bash
cat skills/research-pipeline/SKILL.md skills/research-pipeline/templates/CLAUDE.md
```

适用场景：
- 自己写的 agent / RAG 系统
- ChatGPT Custom GPT 的 "Instructions" 字段
- Claude API 的 `system` 参数
- LangChain / LlamaIndex 的 system message

纯 Markdown，不依赖任何工具特定语法。

---

## 5. 通用 vs 项目专属

`utils_template.py` 只保留**任何数据分析项目通用**的部分：

| 保留（通用 30-40%） | 移除（本项目专属） |
|--------------------|------------------|
| 统计函数（freq_table / likert_stats / crosstab_chi2 / kruskal_test / spearman_corr / 效应量 / 置信区间 / 多重比较校正）| `PROVINCE_MAP`、东中西部映射 |
| 清洗工具（直线作答检测、正反向矛盾、IQR/zscore 异常值） | `VAR_MAP`（87 列问卷题名映射） |
| Plotly 主题与配色 | `MATRIX_LIKERT`（问卷 Likert 编码表） |
| 复查辅助函数 | `PANEL_VARS`（题目板块分组） |

新项目使用时，业务专属配置应放在 `data/config/*.json`，由 `utils.load_config()` 加载。

---

## 6. 验证 skill 安装成功的统一方法

不管挂到哪个 agent，问以下四个问题，正确答案表明规范生效：

| 问题 | 期望回答 | 检查点 |
|------|---------|--------|
| "我有一个 5 点 Likert 题，三个地区比较，每组 n≈20，能用 ANOVA 吗？" | 应**询问分布形态**、提示样本偏小时倾向 Kruskal-Wallis，并要求把决策依据写入 `method.md`；同时提醒报告 epsilon squared 等效应量 | 方法学透明性 |
| "我清洗完直接生成报告可以吗？" | **不可以**，必须先过 99 复查 | 流水线纪律 |
| "Plotly 图表只输出 HTML 行吗？" | **不行**，必须同时输出 PNG 300DPI | 可视化纪律 |
| "我用了 ANOVA 处理量表数据，需要写理由吗？" | **需要**，要在 `method.md` 中说明（复合分数 / 样本量 / 分布近似 / 领域惯例），并报告效应量与必要的稳健性对照 | 方法选择文档化 |

四题全对 → skill 真的在工作。任一题答错 → 规范没读到，检查文件位置与 frontmatter。

---

## 7. 版本

- **v1.1.1**（2026-06-05）：稳健性修复
  - 修复 SKILL.md frontmatter YAML 解析问题
  - 修复多选题、直线作答、卡方、Kruskal、Mann-Whitney、Wilson CI、加权均值等边界场景
  - 同步 README / SKILL.md / CLAUDE.md 的方法依据与工具函数表述
- **v1.1**（2026-06-05）：统计方法升级
  - 增加分析目的决策框架、效应量、置信区间、多重比较校正、缺失/权重/稳健性、模型层方法
  - utils 模板新增 Wilson CI、bootstrap CI、Cramer's V、Cohen's d、Kruskal epsilon squared、Cronbach alpha、BH/Holm 校正
- **v1.0**（2026-06-05）：首版，从 `education-stat-survey-2026` 提炼
  - SKILL.md 符合 skills.sh 标准 frontmatter
  - bundled templates/ 包含 CLAUDE.md + utils + pyproject
  - 覆盖 Claude Code / Codex / Cursor / Gemini / Cline / Windsurf / Copilot / Qoder 安装路径

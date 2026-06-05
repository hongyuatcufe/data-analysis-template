"""
通用工具骨架 —— research-pipeline skill 配套

复制到项目 scripts/utils.py 后按需扩展。
所有函数设计为无业务硬编码，可跨项目复用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

# ─── 路径常量 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
CONFIG_DIR = DATA_DIR / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"
TABLES_DIR = OUTPUT_DIR / "tables"
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORT_DIR = PROJECT_ROOT / "report"

for d in (CLEANED_DIR, CONFIG_DIR, TABLES_DIR, CHARTS_DIR, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ─── 配色 ────────────────────────────────────────────────
PRIMARY = "#2563eb"
SECONDARY = "#3b82f6"
ACCENT = "#f59e0b"
POSITIVE = "#10b981"
NEGATIVE = "#ef4444"
NEUTRAL = "#64748b"
GRID = "#f1f5f9"

CATEGORICAL_COLORS = [
    "#2563eb", "#f59e0b", "#10b981", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#64748b",
]
SEQUENTIAL_BLUE = ["#dbeafe", "#93c5fd", "#3b82f6", "#1d4ed8", "#1e3a8a"]
DIVERGING = ["#ef4444", "#f59e0b", "#e5e7eb", "#3b82f6", "#1e3a8a"]

CHINESE_FONT = "PingFang SC, Microsoft YaHei, sans-serif"


# ─── 配置加载 ────────────────────────────────────────────
def load_config(name: str) -> dict:
    """从 data/config/<name>.json 加载配置"""
    path = CONFIG_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ─── 数据质量探查 ────────────────────────────────────────
def data_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """逐列输出类型、缺失率、唯一值数、样例值，用于 explore 阶段"""
    rows = []
    total = len(df)
    for col in df.columns:
        s = df[col]
        non_null = s.notna().sum()
        unique = s.nunique(dropna=True)
        sample = s.dropna().unique()[:3].tolist()
        rows.append({
            "column": col,
            "dtype": str(s.dtype),
            "non_null_pct": round(100 * non_null / total, 2) if total else np.nan,
            "unique": unique,
            "sample": ", ".join(map(str, sample)),
        })
    return pd.DataFrame(rows)


# ─── 清洗规则 ────────────────────────────────────────────
def detect_duplicates(df: pd.DataFrame, subset: list | None = None) -> pd.Series:
    """返回 bool Series 标记重复行（保留首条）"""
    return df.duplicated(subset=subset, keep="first")


def detect_straight_line(df: pd.DataFrame, matrix_groups: dict[str, list[str]]) -> pd.Series:
    """
    检测矩阵题"直线作答"。
    matrix_groups: {"Q7": ["Q7_1","Q7_2",...], "Q15": [...], ...}
    判定：每个矩阵组内至少有 2 个有效作答，且有效作答全部相同。
    """
    if not matrix_groups:
        return pd.Series(False, index=df.index)

    flags = pd.Series(False, index=df.index)
    for cols in matrix_groups.values():
        group = df[cols]
        valid_count = group.notna().sum(axis=1)
        same_in_group = (valid_count >= 2) & (group.nunique(axis=1, dropna=True) == 1)
        flags |= same_in_group
    return flags


def detect_contradiction(
    df: pd.DataFrame,
    positive_cols: list[str],
    negative_cols: list[str],
    threshold: int = 4,
) -> pd.Series:
    """
    检测正反向题逻辑矛盾。
    例：Q7_1/Q7_2 正向（高=负担重），Q7_4/Q7_5 反向（高=负担轻）
    矛盾 = 任一正向 >= threshold 且 任一反向 >= threshold
    """
    pos_high = (df[positive_cols] >= threshold).any(axis=1)
    neg_high = (df[negative_cols] >= threshold).any(axis=1)
    return pos_high & neg_high


def detect_outliers(
    df: pd.DataFrame, col: str, method: str = "iqr", k: float = 1.5
) -> pd.Series:
    """method: iqr | zscore | range（range 需用户后处理）"""
    s = df[col].dropna()
    if method == "iqr":
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        return (df[col] < lo) | (df[col] > hi)
    if method == "zscore":
        z = np.abs((df[col] - s.mean()) / s.std())
        return z > k
    raise ValueError(f"unknown method: {method}")


def write_cleaning_log(
    log_rows: list[dict], out_path: Path | str = None
) -> pd.DataFrame:
    """log_rows: [{rule, hit, kept, removed_ids}, ...]"""
    df = pd.DataFrame(log_rows)
    if out_path is None:
        out_path = TABLES_DIR / "00_cleaning_log.xlsx"
    df.to_excel(out_path, index=False)
    return df


# ─── 描述统计 ────────────────────────────────────────────
def freq_table(s: pd.Series, label_map: dict | None = None) -> pd.DataFrame:
    """单选/分类：频数 + 百分比（分母 = 有效样本）"""
    counts = s.value_counts(dropna=True)
    pct = (counts / counts.sum() * 100).round(2)
    out = pd.DataFrame({"value": counts.index, "n": counts.values, "pct": pct.values})
    if label_map:
        out["label"] = out["value"].map(label_map)
    return out


def multi_count(
    df: pd.DataFrame,
    cols: Sequence[str],
    label_map: dict | None = None,
    checked_values: Sequence = (1, True, "1", "是", "已选", "选中", "√", "✓", "Y", "Yes", "yes"),
) -> pd.DataFrame:
    """多选题：勾选率（分母 = 总样本 = len(df)）。支持 0/1 与常见中文/数值勾选值。"""
    total = len(df)
    checked = {str(v).strip() for v in checked_values}
    # 针对数值列提取对应的数值型勾选值
    checked_numeric = []
    for v in checked_values:
        try:
            checked_numeric.append(float(v))
        except (ValueError, TypeError):
            pass
            
    rows = []
    for c in cols:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            # 如果用户自定义了勾选值，且当前列为数值型，则精确过滤勾选值；否则默认使用 >0 判定
            if len(checked_numeric) > 0 and set(checked_values) != {str(v).strip() for v in (1, True, "1", "是", "已选", "选中", "√", "✓", "Y", "Yes", "yes")}:
                n = int(s.isin(checked_numeric).sum())
            else:
                n = int(s.fillna(0).astype(float).gt(0).sum())
        else:
            n = int(s.dropna().astype(str).str.strip().isin(checked).sum())
        rows.append({
            "item": c,
            "label": (label_map or {}).get(c, c),
            "n": n,
            "pct": round(100 * n / total, 2) if total else np.nan,
        })
    return pd.DataFrame(rows)


def likert_stats(
    df: pd.DataFrame, cols: Sequence[str], scale: int = 5,
    label_map: dict | None = None, levels: Sequence[int] | None = None
) -> pd.DataFrame:
    """有序量表：均值 + SD + 完整频数分布。允许通过 levels 自定义分值范围（如 [-2, -1, 0, 1, 2]）"""
    rows = []
    valid_levels = list(levels) if levels is not None else list(range(1, scale + 1))
    for c in cols:
        s = df[c].dropna()
        row = {
            "item": c,
            "label": (label_map or {}).get(c, c),
            "n": len(s),
            "mean": round(s.mean(), 3) if len(s) else np.nan,
            "SD": round(s.std(), 3) if len(s) > 1 else np.nan,
        }
        for k in valid_levels:
            n_k = int((s == k).sum())
            row[f"n_{k}"] = n_k
            row[f"pct_{k}"] = round(100 * n_k / len(s), 2) if len(s) else 0
        rows.append(row)
    return pd.DataFrame(rows)


def text_stats(s: pd.Series) -> dict:
    """开放题：作答率 + 字数统计"""
    total = len(s)
    answered = s.dropna().astype(str).str.strip()
    answered = answered[answered != ""]
    lens = answered.str.len()
    return {
        "response_rate": round(100 * len(answered) / total, 2) if total else np.nan,
        "mean_len": round(lens.mean(), 1) if len(lens) else 0,
        "median_len": float(lens.median()) if len(lens) else 0,
        "max_len": int(lens.max()) if len(lens) else 0,
    }


# ─── 推断统计 ────────────────────────────────────────────
def wilson_ci(success: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """比例的 Wilson 置信区间，返回百分比下限/上限。"""
    if n <= 0:
        return (np.nan, np.nan)
    if success < 0 or success > n:
        raise ValueError("success must be between 0 and n")
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = success / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (round((center - half) * 100, 2), round((center + half) * 100, 2))


def mean_ci(s: pd.Series, confidence: float = 0.95) -> tuple[float, float]:
    """均值 t 置信区间。"""
    x = s.dropna().astype(float)
    n = len(x)
    if n < 2:
        return (np.nan, np.nan)
    se = x.std(ddof=1) / np.sqrt(n)
    t = stats.t.ppf(1 - (1 - confidence) / 2, df=n - 1)
    m = x.mean()
    return (round(m - t * se, 3), round(m + t * se, 3))


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    confidence: float = 0.95,
    n_boot: int = 2000,
    random_state: int = 42,
) -> tuple[float, float]:
    """通用 bootstrap 置信区间。"""
    x = pd.Series(values).dropna().astype(float).to_numpy()
    if len(x) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(random_state)
    stats_boot = []
    for _ in range(n_boot):
        sample = rng.choice(x, size=len(x), replace=True)
        stats_boot.append(statistic(sample))
    alpha = (1 - confidence) / 2
    lo, hi = np.quantile(stats_boot, [alpha, 1 - alpha])
    return (round(float(lo), 3), round(float(hi), 3))


def pearson_r_ci(r: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Pearson r 的 Fisher z 置信区间。"""
    if n <= 3 or abs(r) >= 1:
        return (np.nan, np.nan)
    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    crit = stats.norm.ppf(1 - (1 - confidence) / 2)
    lo, hi = np.tanh([z - crit * se, z + crit * se])
    return (round(float(lo), 3), round(float(hi), 3))


def cramers_v(table: pd.DataFrame | np.ndarray) -> float:
    """Cramer's V for chi-square association strength."""
    arr = np.asarray(table)
    if arr.size == 0:
        return np.nan
    n = arr.sum()
    if n == 0:
        return np.nan
    r, k = arr.shape
    denom = n * (min(r - 1, k - 1))
    if denom <= 0:
        return np.nan
    chi2 = stats.chi2_contingency(arr, correction=False)[0]
    return round(float(np.sqrt(chi2 / denom)), 3)


def cohens_d(x: Sequence[float], y: Sequence[float], hedges: bool = False) -> float:
    """两组均值差效应量 Cohen's d；hedges=True 时返回小样本校正 g。"""
    a = pd.Series(x).dropna().astype(float).to_numpy()
    b = pd.Series(y).dropna().astype(float).to_numpy()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    if pooled == 0:
        return np.nan
    d = (a.mean() - b.mean()) / pooled
    if hedges:
        correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
        d *= correction
    return round(float(d), 3)


def rank_biserial_from_u(u: float, n1: int, n2: int) -> float:
    """Mann-Whitney U 的 rank-biserial correlation；正值表示第一组整体更高。"""
    if n1 <= 0 or n2 <= 0:
        return np.nan
    return round(float((2 * u) / (n1 * n2) - 1), 3)


def epsilon_squared_kruskal(h: float, n: int, k: int) -> float:
    """Kruskal-Wallis epsilon squared effect size。"""
    if n <= k:
        return np.nan
    return round(float((h - k + 1) / (n - k)), 3)


def eta_squared_anova(groups: Sequence[Sequence[float]]) -> float:
    """One-way ANOVA eta squared。"""
    arrays = [pd.Series(g).dropna().astype(float).to_numpy() for g in groups]
    arrays = [a for a in arrays if len(a) > 0]
    if len(arrays) < 2:
        return np.nan
    all_values = np.concatenate(arrays)
    grand_mean = all_values.mean()
    ss_between = sum(len(a) * (a.mean() - grand_mean) ** 2 for a in arrays)
    ss_total = sum((x - grand_mean) ** 2 for x in all_values)
    return round(float(ss_between / ss_total), 3) if ss_total else np.nan


def _validate_p_values(p_values: Sequence[float]) -> np.ndarray:
    """校验 p 值范围，允许 NaN 并在校正函数中原样保留。"""
    p = np.asarray(p_values, dtype=float)
    invalid = (~np.isnan(p)) & ((p < 0) | (p > 1))
    if invalid.any():
        raise ValueError("p-values must be between 0 and 1 or NaN")
    return p


def p_adjust_bh(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg FDR 校正。"""
    p = _validate_p_values(p_values)
    adjusted = np.full(len(p), np.nan)
    valid = ~np.isnan(p)
    p_valid = p[valid]
    n = len(p_valid)
    if n == 0:
        return [np.nan for _ in p]
    order = np.argsort(p_valid)
    adjusted_valid = np.empty(n)
    prev = 1.0
    for rank, idx in enumerate(order[::-1], start=1):
        true_rank = n - rank + 1
        val = min(prev, p_valid[idx] * n / true_rank)
        adjusted_valid[idx] = val
        prev = val
    adjusted[valid] = adjusted_valid
    return [round(float(x), 4) for x in adjusted]


def p_adjust_holm(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni 校正。"""
    p = _validate_p_values(p_values)
    adjusted = np.full(len(p), np.nan)
    valid = ~np.isnan(p)
    p_valid = p[valid]
    n = len(p_valid)
    if n == 0:
        return [np.nan for _ in p]
    order = np.argsort(p_valid)
    adjusted_valid = np.empty(n)
    prev = 0.0
    for rank, idx in enumerate(order, start=1):
        val = max(prev, min(1.0, (n - rank + 1) * p_valid[idx]))
        adjusted_valid[idx] = val
        prev = val
    adjusted[valid] = adjusted_valid
    return [round(float(x), 4) for x in adjusted]


def cronbach_alpha(df: pd.DataFrame, cols: Sequence[str]) -> float:
    """多题量表内部一致性 Cronbach's alpha。"""
    items = df[list(cols)].dropna().astype(float)
    k = len(cols)
    if k < 2 or len(items) < 2:
        return np.nan
    item_vars = items.var(axis=0, ddof=1)
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return np.nan
    alpha = k / (k - 1) * (1 - item_vars.sum() / total_var)
    return round(float(alpha), 3)


def crosstab_chi2(df: pd.DataFrame, var1: str, var2: str) -> dict:
    """
    分类 × 分类：返回频数表 / 行% / 列% / 卡方统计量 / p / dof / Cramer's V / 期望频数警告。
    若期望频数<5占比>20%，reported=False，报告中不应引用 p 值作为显著性结论。
    """
    ct = pd.crosstab(df[var1], df[var2])
    if ct.empty or ct.size == 0:
        return {
            "table": ct,
            "row_pct": ct,
            "col_pct": ct,
            "chi2": np.nan,
            "p": np.nan,
            "dof": 0,
            "cramers_v": np.nan,
            "expected_small_pct": np.nan,
            "reported": False,
            "warning": "无有效交叉数据，不报告显著性",
        }
    chi2, p, dof, expected = stats.chi2_contingency(ct)
    if dof == 0:
        return {
            "table": ct,
            "row_pct": ct.div(ct.sum(axis=1), axis=0).mul(100).round(2),
            "col_pct": ct.div(ct.sum(axis=0), axis=1).mul(100).round(2),
            "chi2": round(chi2, 3),
            "p": round(p, 4),
            "dof": dof,
            "cramers_v": np.nan,
            "expected_small_pct": np.nan,
            "reported": False,
            "warning": "至少一个变量只有一个有效水平，不报告关联显著性",
        }
    expected_small_pct = (expected < 5).mean() * 100
    reported = expected_small_pct <= 20
    return {
        "table": ct,
        "row_pct": ct.div(ct.sum(axis=1), axis=0).mul(100).round(2),
        "col_pct": ct.div(ct.sum(axis=0), axis=1).mul(100).round(2),
        "chi2": round(chi2, 3),
        "p": round(p, 4),
        "dof": dof,
        "cramers_v": cramers_v(ct),
        "expected_small_pct": round(expected_small_pct, 1),
        "reported": reported,
        "warning": "期望频数<5 占比 >20%，不报告显著性" if expected_small_pct > 20 else "",
    }


def kruskal_test(df: pd.DataFrame, group_col: str, value_col: str) -> dict:
    """有序 × 分类（k>2）：Kruskal-Wallis"""
    groups = [g[value_col].dropna().astype(float).values for _, g in df.groupby(group_col)]
    groups = [g for g in groups if len(g) > 0]
    if len(groups) < 2:
        return {
            "H": np.nan,
            "p": np.nan,
            "k": len(groups),
            "n": len(df[value_col].dropna()),
            "epsilon_squared": np.nan,
            "warning": f"有效分组不足 2 组 (仅有 {len(groups)} 组)，无法进行 Kruskal-Wallis 检验",
        }
    n = sum(len(g) for g in groups)
    if len(np.unique(np.concatenate(groups))) == 1:
        return {
            "H": 0.0,
            "p": 1.0,
            "k": len(groups),
            "n": n,
            "epsilon_squared": 0.0,
            "warning": "各组数值完全相同，不存在可检验差异",
        }
    h, p = stats.kruskal(*groups)
    return {
        "H": round(h, 3),
        "p": round(p, 4),
        "k": len(groups),
        "n": n,
        "epsilon_squared": epsilon_squared_kruskal(h, n, len(groups)),
        "warning": "",
    }


def mannwhitney_test(df: pd.DataFrame, group_col: str, value_col: str) -> dict:
    """有序 × 分类（k=2）：Mann-Whitney U"""
    group_items = [
        (name, g[value_col].dropna().astype(float).values)
        for name, g in df.groupby(group_col)
    ]
    group_items = [(name, values) for name, values in group_items if len(values) > 0]
    if len(group_items) != 2:
        return {
            "group1": None,
            "group2": None,
            "U": np.nan,
            "p": np.nan,
            "n1": 0,
            "n2": 0,
            "rank_biserial": np.nan,
            "warning": f"Mann-Whitney 检验要求刚好有 2 个非空组，当前有 {len(group_items)} 组",
        }
    (group1, a), (group2, b) = group_items
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "group1": group1,
        "group2": group2,
        "U": round(u, 3),
        "p": round(p, 4),
        "n1": len(a),
        "n2": len(b),
        "rank_biserial": rank_biserial_from_u(u, len(a), len(b)),
    }


def spearman_corr(df: pd.DataFrame, cols: Sequence[str]) -> dict:
    """有序 × 有序：Spearman 相关，返回 rho 和 p 矩阵。"""
    sub = df[list(cols)].dropna()
    rho, p = stats.spearmanr(sub)
    if len(cols) == 2:
        return {
            "rho": round(float(rho), 3),
            "p": round(float(p), 4),
            "n": len(sub),
        }
    return {
        "rho": pd.DataFrame(rho, index=cols, columns=cols).round(3),
        "p": pd.DataFrame(p, index=cols, columns=cols).round(4),
        "n": len(sub),
    }


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    """加权均值（自动对齐并剔除任意一方包含 NaN 的观测值，防算出力 nan）"""
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if len(v) != len(w):
        raise ValueError("values and weights must have the same length")
    
    # 过滤 NaN 配对
    valid = ~np.isnan(v) & ~np.isnan(w)
    v_valid = v[valid]
    w_valid = w[valid]
    
    total_weight = w_valid.sum()
    if total_weight == 0:
        return np.nan
    return float((v_valid * w_valid).sum() / total_weight)


# ─── Excel 输出辅助 ──────────────────────────────────────
def safe_sheet_name(name: str, max_len: int = 31) -> str:
    """Excel sheet 名安全处理（去除非法字符 + 长度限制）"""
    illegal = '[]:*?/\\'
    for c in illegal:
        name = name.replace(c, "_")
    return name[:max_len]


def write_excel_sheets(sheets: dict[str, pd.DataFrame], path: Path | str) -> None:
    """sheets: {sheet_name: DataFrame}"""
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=safe_sheet_name(name), index=False)


# ─── Plotly 主题 ─────────────────────────────────────────
def apply_plotly_theme(fig, title: str = "", height: int = 500):
    """统一应用项目配色和字体"""
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, family=CHINESE_FONT)),
        font=dict(family=CHINESE_FONT, color="#1e293b", size=12),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        hoverlabel=dict(bgcolor="#1e293b", font_color="white"),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor=NEUTRAL, borderwidth=1),
    )
    fig.update_xaxes(gridcolor=GRID, gridwidth=0.8, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, gridwidth=0.8, zeroline=False)
    return fig


def export_html_png(fig, name: str, width: int = 900, height: int = 600) -> None:
    """同时输出 HTML + 300DPI PNG"""
    html_path = CHARTS_DIR / f"{name}.html"
    png_path = CHARTS_DIR / f"{name}.png"
    fig.write_html(html_path, include_plotlyjs="cdn")
    try:
        fig.write_image(png_path, width=width, height=height, scale=3)
    except Exception as e:
        print(f"[warn] PNG export failed for {name}: {e}. Ensure 'kaleido' is installed.")


# ─── 复查辅助 ────────────────────────────────────────────
def audit_check(name: str, expected, actual, tol: float = 0.01) -> dict:
    """
    通用复查检查项。数值类按容差判定，其余按相等。
    特殊处理了双 NaN 匹配（即两者均为空时判定为对账通过 ✅）。
    返回 {check, expected, actual, status, diff}
    """
    import math
    
    # 判断是否为 NaN/None/pd.NA
    def is_null(val):
        if val is None or val is pd.NA:
            return True
        if isinstance(val, (int, float)) and math.isnan(val):
            return True
        return False

    if is_null(expected) and is_null(actual):
        return {"check": name, "expected": np.nan, "actual": np.nan, "diff": 0.0, "status": "✅"}
    if is_null(expected) or is_null(actual):
        return {"check": name, "expected": expected, "actual": actual, "diff": np.nan, "status": "❌"}

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        diff = abs(expected - actual)
        status = "✅" if diff <= tol else "❌"
        return {"check": name, "expected": expected, "actual": actual, "diff": diff, "status": status}
    
    status = "✅" if expected == actual else "❌"
    return {"check": name, "expected": expected, "actual": actual, "diff": None, "status": status}


def write_audit_report(rows: list[dict], path: Path | str = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if path is None:
        path = TABLES_DIR / "99_audit_report.xlsx"
    df.to_excel(path, index=False)
    failed = (df["status"] == "❌").sum()
    print(f"Audit: {len(df)} checks, {failed} failed")
    return df

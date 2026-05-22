#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告图表生成脚本 — 生成 9 张发表级图片供 LaTeX 报告使用。
运行方式（在 restaurant_analysis/ 根目录下）：
    python analysis/generate_figures.py
输出目录：outputs/figures/
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.data_loader import ReviewDataLoader
from analysis.preprocessor import ReviewPreprocessor
from analysis.analyzer import TabularAnalyzer, SequentialAnalyzer
from analysis.text_analysis import TextAnalyzer

# ── 全局样式 ──────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.titlesize":    12,
    "axes.titleweight":  "bold",
    "axes.labelsize":    10.5,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.labelsize":   9.5,
    "ytick.labelsize":   9.5,
    "legend.fontsize":   9,
    "figure.dpi":        120,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "savefig.pad_inches": 0.12,
})

NAVY   = "#1a4d8c"
BLUE   = "#2980b9"
GREEN  = "#27ae60"
ORANGE = "#e67e22"
RED    = "#c0392b"
GRAY   = "#95a5a6"

OUT = "outputs/figures"
os.makedirs(OUT, exist_ok=True)


def _save(name: str):
    plt.savefig(os.path.join(OUT, name))
    plt.close()
    print(f"  -> {name}")


# ══════════════════════════════════════════════════════════════
# 数据加载
# ══════════════════════════════════════════════════════════════
def _load():
    print("[数据] 加载并预处理...")
    df_raw = ReviewDataLoader.load("data/sample_reviews.csv")
    df = ReviewPreprocessor().fit_transform(df_raw)
    print(f"  {len(df):,} 条有效评论")
    return df


# ══════════════════════════════════════════════════════════════
# Fig 1 — 评分分布（J 型）
# ══════════════════════════════════════════════════════════════
def fig_rating_distribution(df: pd.DataFrame):
    score  = pd.to_numeric(df["review_score"], errors="coerce").dropna()
    counts = score.value_counts().sort_index()
    pcts   = counts / len(score) * 100

    fig, ax = plt.subplots(figsize=(6, 4))
    bar_colors = [RED, ORANGE, GRAY, BLUE, NAVY]
    bars = ax.bar(counts.index, pcts, color=bar_colors,
                  width=0.6, edgecolor="white", linewidth=0.8)

    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, pct + 0.4,
                f"{pct:.1f}%", ha="center", va="bottom", fontsize=9)

    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["1★\n(Negative)", "2★\n(Negative)",
                         "3★\n(Neutral)", "4★\n(Positive)", "5★\n(Positive)"])
    ax.set_ylabel("Proportion (%)")
    ax.set_title("Review Score Distribution")
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save("fig_rating_distribution.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 2 — Wilson vs 贝叶斯排名对比
# ══════════════════════════════════════════════════════════════
def fig_ranking_comparison(df: pd.DataFrame):
    ta     = TabularAnalyzer()
    wilson = ta.wilson_ranking(df, min_reviews=10).head(100)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # 左：散点，颜色=漂移量
    drift = wilson["rank_drift"].abs()
    sc = ax1.scatter(wilson["wilson_rank"], wilson["bayes_rank"],
                     c=drift, cmap="RdYlGn_r", s=45, alpha=0.75,
                     vmin=0, vmax=drift.quantile(0.9), zorder=3)
    ax1.plot([1, 100], [1, 100], "k--", lw=1.2, alpha=0.5, label="No drift (diagonal)")
    ax1.set_xlabel("Wilson Rank")
    ax1.set_ylabel("Bayesian Rank")
    ax1.set_title("Wilson vs Bayesian Rank (Top 100)")
    plt.colorbar(sc, ax=ax1, label="|Rank Drift|", shrink=0.88)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, linestyle="--")

    # 右：漂移分布直方图
    ax2.hist(wilson["rank_drift"], bins=20, color=BLUE,
             edgecolor="white", linewidth=0.6, alpha=0.85)
    ax2.axvline(0, color="k", linestyle="--", lw=1.5, label="Zero drift")
    ax2.set_xlabel("Rank Drift  (Bayesian rank − Wilson rank)")
    ax2.set_ylabel("Number of Restaurants")
    ax2.set_title("Distribution of Rank Drift")
    ax2.legend()
    ax2.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax2.set_axisbelow(True)

    fig.tight_layout()
    _save("fig_ranking_comparison.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 3 — KMeans 餐厅聚类
# ══════════════════════════════════════════════════════════════
def fig_restaurant_clusters(df: pd.DataFrame):
    ta              = TabularAnalyzer()
    detail, summary = ta.restaurant_clustering(df, n_clusters=4)
    cmap = {"Premium": GREEN, "Good": BLUE, "Average": ORANGE, "At Risk": RED}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # 左：均分 vs log(评论量) 散点
    for label, grp in detail.groupby("cluster_label"):
        ax1.scatter(grp["avg_score"], np.log1p(grp["review_count"]),
                    c=cmap.get(label, GRAY), label=label,
                    s=18, alpha=0.55, edgecolors="none")
    ax1.set_xlabel("Average Score")
    ax1.set_ylabel("log(1 + Review Count)")
    ax1.set_title("Restaurant Clusters: Score vs Volume")
    ax1.legend(title="Cluster")
    ax1.grid(True, alpha=0.3, linestyle="--")

    # 右：各聚类店铺数量柱图
    x = np.arange(len(summary))
    bars = ax2.bar(x, summary["shop_count"],
                   color=[cmap.get(l, GRAY) for l in summary["cluster_label"]],
                   width=0.55, edgecolor="white", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(summary["cluster_label"])
    ax2.set_ylabel("Number of Restaurants")
    ax2.set_title("Restaurant Count per Cluster")
    ax2.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax2.set_axisbelow(True)
    for bar, row in zip(bars, summary.itertuples()):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 15,
                 f"avg={row.mean_score:.2f}", ha="center", va="bottom", fontsize=8.5)

    fig.tight_layout()
    _save("fig_restaurant_clusters.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 4 — 小时分布
# ══════════════════════════════════════════════════════════════
def fig_hourly_pattern(df: pd.DataFrame):
    sa     = SequentialAnalyzer()
    hourly = sa.hourly_pattern(df)

    colors = [RED if h in range(18, 23) else
              (ORANGE if h in range(11, 15) else BLUE)
              for h in hourly["review_hour"]]

    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.bar(hourly["review_hour"], hourly["count"],
           color=colors, width=0.75, edgecolor="white", linewidth=0.4)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Review Count")
    ax.set_title("Review Volume by Hour of Day")
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(color=ORANGE, label="Lunch Peak (11–14 h)"),
        mpatches.Patch(color=RED,    label="Dinner Peak (18–22 h)"),
        mpatches.Patch(color=BLUE,   label="Other Hours"),
    ]
    ax.legend(handles=legend_handles, loc="upper left")
    fig.tight_layout()
    _save("fig_hourly_pattern.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 5 — STL 时序分解（4 面板）
# ══════════════════════════════════════════════════════════════
def fig_stl_decomposition(df: pd.DataFrame):
    sa     = SequentialAnalyzer()
    decomp = sa.trend_decomposition(df).dropna(subset=["trend"])
    method = decomp["method"].iloc[0]
    x      = np.arange(len(decomp))

    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    panels = [
        ("count",    "Observed",  NAVY,   False),
        ("trend",    "Trend",     GREEN,  False),
        ("seasonal", "Seasonal",  BLUE,   True),
        ("residual", "Residual",  RED,    True),
    ]
    for ax, (col, lbl, color, fill) in zip(axes, panels):
        vals = decomp[col].values
        if fill:
            ax.fill_between(x, vals, alpha=0.65, color=color, label=lbl)
            ax.axhline(0, color="k", lw=0.8, linestyle="--")
        else:
            ax.plot(x, vals, color=color, lw=1.3, label=lbl)
        ax.set_ylabel(lbl)
        ax.legend(loc="upper right", fontsize=9)
        ax.yaxis.grid(True, alpha=0.3, linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_title(f"STL Decomposition of Monthly Review Volume  [{method}]")
    axes[-1].set_xlabel("Month Index (2004 → 2020)")

    # 标注 2020 年疫情异常区
    covid_start = decomp[decomp["year_month"] >= "2020-03"].index
    if len(covid_start):
        ci = x[decomp.index.get_loc(covid_start[0])]
        for ax in axes:
            ax.axvspan(ci, x[-1], alpha=0.08, color=RED)
        axes[3].text(ci + 1, axes[3].get_ylim()[0] * 0.8,
                     "COVID-19", color=RED, fontsize=8.5)

    fig.tight_layout()
    _save("fig_stl_decomposition.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 6 — KMeans RFM 聚类
# ══════════════════════════════════════════════════════════════
def fig_rfm_clustering(df: pd.DataFrame):
    sa                 = SequentialAnalyzer()
    rfm_detail, rfm_sum = sa.rfm_clustering(df, n_clusters=5)
    seg_colors = {"Champions": GREEN, "Loyal": BLUE, "Potential": ORANGE,
                  "At Risk": RED, "Inactive": GRAY}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # 左：R vs F 散点
    for seg, grp in rfm_detail.groupby("km_segment"):
        samp = grp.sample(min(len(grp), 600), random_state=42)
        ax1.scatter(samp["R"], samp["F"],
                    c=seg_colors.get(seg, GRAY), label=seg,
                    s=10, alpha=0.45, edgecolors="none")
    ax1.set_xlabel("Recency (days since last review)")
    ax1.set_ylabel("Frequency (review count)")
    ax1.set_title("KMeans RFM: Recency vs Frequency")
    ax1.legend(title="Segment", markerscale=2.5)
    ax1.grid(True, alpha=0.3, linestyle="--")

    # 右：各聚类用户数
    x = np.arange(len(rfm_sum))
    bars = ax2.bar(x, rfm_sum["user_count"],
                   color=[seg_colors.get(l, GRAY) for l in rfm_sum["km_segment"]],
                   width=0.6, edgecolor="white", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(rfm_sum["km_segment"], rotation=15, ha="right")
    ax2.set_ylabel("User Count")
    ax2.set_title("User Count per KMeans RFM Segment")
    ax2.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax2.set_axisbelow(True)
    total = rfm_sum["user_count"].sum()
    for bar, row in zip(bars, rfm_sum.itertuples()):
        pct = row.user_count / total * 100
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 40,
                 f"{pct:.1f}%", ha="center", va="bottom", fontsize=8.5)

    fig.tight_layout()
    _save("fig_rfm_clustering.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 7 — LDA 主题分布
# ══════════════════════════════════════════════════════════════
def fig_lda_topics(df: pd.DataFrame):
    ta_txt = TextAnalyzer()
    topics = ta_txt.topic_modeling(df, n_topics=8, n_words=5)
    topics["label"] = topics.apply(
        lambda r: f"T{int(r['topic_id'])}: " +
                  ", ".join(r["top_words"].split(", ")[:4]),
        axis=1
    )
    topics = topics.sort_values("proportion")

    fig, ax = plt.subplots(figsize=(8, 5))
    palette = plt.cm.Blues(np.linspace(0.35, 0.85, len(topics)))
    bars = ax.barh(topics["label"], topics["proportion"],
                   color=palette, edgecolor="white", linewidth=0.6)
    for bar, val in zip(bars, topics["proportion"]):
        ax.text(val + 0.15, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9)

    ax.set_xlabel("Proportion of Reviews (%)")
    ax.set_title("LDA Topic Distribution  (k = 8)")
    ax.xaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save("fig_lda_topics.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 8 — 维度-情感热力图
# ══════════════════════════════════════════════════════════════
def fig_aspect_sentiment(df: pd.DataFrame):
    ta_txt = TextAnalyzer()
    matrix = ta_txt.aspect_sentiment_matrix(df)

    heat = (matrix
            .set_index("dimension")
            [["positive_pct", "neutral_pct", "negative_pct"]]
            .rename(columns={"positive_pct": "Positive",
                              "neutral_pct":  "Neutral",
                              "negative_pct": "Negative"}))

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    sns.heatmap(heat, annot=True, fmt=".1f", cmap="RdYlGn",
                linewidths=0.5, linecolor="white",
                vmin=0, vmax=82,
                annot_kws={"size": 10},
                cbar_kws={"label": "Proportion (%)"},
                ax=ax)
    ax.set_title("Aspect–Sentiment Matrix  (%)")
    ax.set_xlabel("Sentiment Polarity")
    ax.set_ylabel("Service Dimension")
    ax.tick_params(axis="x", rotation=0)
    ax.tick_params(axis="y", rotation=0)
    fig.tight_layout()
    _save("fig_aspect_sentiment.pdf")


# ══════════════════════════════════════════════════════════════
# Fig 9 — 情感分类器评估
# ══════════════════════════════════════════════════════════════
def fig_classifier_metrics(df: pd.DataFrame):
    ta_txt = TextAnalyzer()
    result = ta_txt.sentiment_classifier(df, test_size=0.2)
    report = result["report"]
    acc    = result["accuracy"]

    classes  = ["Negative(-1)", "Neutral(0)", "Positive(1)"]
    metrics  = ["precision", "recall", "f1-score"]
    m_labels = ["Precision", "Recall", "F1-Score"]
    m_colors = [NAVY, BLUE, GREEN]
    width    = 0.24

    x   = np.arange(len(classes))
    fig, ax = plt.subplots(figsize=(8, 4.5))

    for i, (metric, label, color) in enumerate(zip(metrics, m_labels, m_colors)):
        vals = [report[c][metric] for c in classes]
        bars = ax.bar(x + i * width, vals, width,
                      label=label, color=color,
                      edgecolor="white", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.005,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=8)

    ax.axhline(acc, color=RED, linestyle="--", lw=1.6,
               label=f"Overall Accuracy = {acc:.4f}")
    ax.set_xticks(x + width)
    ax.set_xticklabels(["Negative", "Neutral", "Positive"])
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.1)
    ax.set_title("Sentiment Classifier Evaluation  (TF-IDF + Logistic Regression)")
    ax.legend(loc="upper left")
    ax.yaxis.grid(True, alpha=0.35, linestyle="--")
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save("fig_classifier_metrics.pdf")


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  Report Figure Generator  (9 figures)")
    print("=" * 55)
    df = _load()

    tasks = [
        ("Rating distribution",     fig_rating_distribution),
        ("Ranking comparison",       fig_ranking_comparison),
        ("Restaurant clusters",      fig_restaurant_clusters),
        ("Hourly pattern",           fig_hourly_pattern),
        ("STL decomposition",        fig_stl_decomposition),
        ("RFM clustering",           fig_rfm_clustering),
        ("LDA topics",               fig_lda_topics),
        ("Aspect-sentiment heatmap", fig_aspect_sentiment),
        ("Classifier metrics",       fig_classifier_metrics),
    ]
    for i, (name, func) in enumerate(tasks, 1):
        print(f"\n[{i}/9] {name}...")
        try:
            func(df)
        except Exception as e:
            print(f"  [WARN] {e}")

    print(f"\nDone. All figures saved to  {OUT}/")

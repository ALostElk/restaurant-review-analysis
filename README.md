# Yelp 餐饮评论多维深度分析框架

> **Yelp Restaurant Review: Multi-dimensional Deep Analysis & Operations Intelligence**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Yelp%20Open%20Dataset-orange)](https://huggingface.co/datasets/Johnnyeee/Yelpdata_663)
[![Report](https://img.shields.io/badge/Report-LaTeX%20PDF-red)](report/yelp_analysis_report.tex)

基于 Yelp 公开数据集（**29,997 条评论 · 8,424 家餐厅 · 503 个城市 · 2004—2020**），
聚焦**表格 / 序列 / 文本**三个核心数据维度，构建涵盖
Wilson Score 置信排名、STL 时序分解、KMeans 多层聚类、LDA 主题建模、
TF-IDF+逻辑回归情感分类的完整分析框架，输出可落地的餐饮运营决策建议。

---

## 研究框架

```
表格数据 (Tabular)          序列数据 (Sequential)        文本数据 (Text)
─────────────────           ──────────────────────       ───────────────────────
EDA 基础统计                小时/月度分布                 维度提及率分析
贝叶斯平滑排名              Z-Score 差评爆发检测          LDA 主题建模 (k=8)
Wilson Score 排名 ★         STL 趋势分解 ★               TF-IDF+LR 情感分类 ★
KMeans 餐厅聚类 ★           线性趋势预测                  维度-情感矩阵 ★
Pearson 相关矩阵            规则 RFM 分层                 BERT/ABSA 数据集构建
                            KMeans RFM 聚类 ★
                                        ↓
                         运营策略层 (Strategy)
                    P0–P3 差评分级预警 · Excel/MD 报告导出
```

★ 标注为相较于基线方法的深化创新点

---

## 目录结构

```
restaurant_analysis/
├── analysis/
│   ├── data_loader.py          # 多源数据加载（CSV / JSON / MongoDB / MySQL）
│   ├── preprocessor.py         # 预处理（清洗、类型转换、衍生特征）
│   ├── analyzer.py             # 表格 & 序列分析（TabularAnalyzer / SequentialAnalyzer）
│   ├── text_analysis.py        # 文本分析（TextAnalyzer）
│   ├── strategy.py             # 运营策略层（AlertSystem / ReportGenerator）
│   ├── generate_figures.py     # 9 张报告图表生成脚本
│   └── run_analysis.py         # CLI 主入口
├── data/
│   ├── load_yelp.py            # 从 HuggingFace 拉取 Yelp 数据（需设置 HF_TOKEN）
│   ├── sample_reviews.csv      # 主评论数据（~30,000 条）
│   └── sample_shops.csv        # 店铺元数据（8,424 家）
├── notebooks/
│   └── restaurant_analysis.ipynb
├── outputs/                    # 运行后自动生成（已加入 .gitignore）
│   ├── figures/                # 9 张 PDF 图表（供 LaTeX 引用）
│   ├── datasets/               # BERT（JSONL）/ ABSA（PyABSA）训练集
│   ├── report.xlsx             # Excel 多 Sheet 运营报告
│   └── report.md               # Markdown 运营摘要
├── report/
│   ├── yelp_analysis_report.tex    # LaTeX 学术报告源文件（含 9 张图）
│   └── README.md                   # LaTeX 编译说明
├── requirements.txt
└── .gitignore
```

---

## 数据集

| 属性 | 详情 |
|---|---|
| 来源 | [Yelp Open Dataset](https://huggingface.co/datasets/Johnnyeee/Yelpdata_663)（HuggingFace） |
| 评论数 | 29,997 条（随机采样自训练集，过滤文本 <5 字符） |
| 餐厅数 | 8,424 家 |
| 城市数 | 503 个（美国 47 州） |
| 时间跨度 | 2004 — 2020 年 |
| 情感分布 | 正面 68.1% · 中性 11.6% · 负面 20.3%（J 型分布） |
| ABSA 维度 | Food / Service / Ambiance / Price / Location |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Yelp 数据

```bash
# 设置 HuggingFace Token（从 https://huggingface.co/settings/tokens 获取）
export HF_TOKEN="hf_your_token_here"      # Linux / macOS
$env:HF_TOKEN = "hf_your_token_here"      # Windows PowerShell

python data/load_yelp.py
```

### 3. 运行分析

```bash
# 全模块（表格 + 序列 + 文本）
python analysis/run_analysis.py

# 单模块运行
python analysis/run_analysis.py --module tabular
python analysis/run_analysis.py --module sequential
python analysis/run_analysis.py --module text

# 指定输出格式
python analysis/run_analysis.py --format excel     # outputs/report.xlsx
python analysis/run_analysis.py --format markdown  # outputs/report.md
```

### 4. 生成报告图表

```bash
python analysis/generate_figures.py
# 生成 9 张 PDF 图表至 outputs/figures/
```

### 5. 编译 LaTeX 学术报告

```bash
cd report
xelatex yelp_analysis_report.tex
xelatex yelp_analysis_report.tex   # 第二遍解析交叉引用
```

> 需安装 XeLaTeX + `ctex` 宏包（推荐 TeX Live 2023+）

---

## 核心分析方法

### 表格数据 — `TabularAnalyzer`

| 方法 | 说明 | 关键参数 |
|---|---|---|
| `eda_summary(df)` | 评论数/店铺数/均分/情感分布基础统计 | — |
| `bayesian_ranking(df)` | 贝叶斯平滑排名，先验 $m=30$，消除小样本偏差 | `min_reviews` |
| `wilson_ranking(df)` | **Wilson Score 95% 置信下界排名**，统计严谨性优于贝叶斯 | `min_reviews=10` |
| `restaurant_clustering(df)` | **KMeans 四象限聚类**（均分×评论量×差评率），自动标注 Premium/Good/Average/At Risk | `n_clusters=4` |
| `correlation_analysis(df)` | 数值特征 Pearson 相关矩阵 | — |

### 序列数据 — `SequentialAnalyzer`

| 方法 | 说明 | 关键参数 |
|---|---|---|
| `hourly_pattern(df)` | 24 小时评论量分布（午间/晚间双峰） | — |
| `monthly_trend(df)` | 月度评论量与均分趋势 | — |
| `burst_detection(df)` | Z-Score 滚动窗口差评爆发检测 | `window=7` |
| `trend_decomposition(df)` | **STL 趋势-季节-残差分解**（周期 12 月，robust=True），数据不足时降级为 CMA-12 | — |
| `forecast_trend(df, steps=6)` | 在 STL 趋势分量上拟合线性回归，外推未来 $n$ 月 | `steps=6` |
| `rfm_segmentation(df)` | 规则四分位 RFM 用户分层（对比基线） | — |
| `rfm_clustering(df)` | **KMeans 数据驱动 RFM**，特征 $[-R, F, M]$ 标准化后 $k$-means，质心综合分自动命名 | `n_clusters=5` |

### 文本数据 — `TextAnalyzer`

| 方法 | 说明 | 关键参数 |
|---|---|---|
| `dimension_coverage(df)` | 五维度提及率与维度内差评率 | — |
| `word_frequency(df)` | 正/负/全部词频 Top-N | `top_n=20` |
| `neg_signal_words(df)` | 差评特异度信号词挖掘 | — |
| `shop_keywords(df)` | 每家店铺高频特色词 | — |
| `topic_modeling(df)` | **LDA 主题建模**（CountVectorizer + 在线学习，$k=8$） | `n_topics=8` |
| `sentiment_classifier(df)` | **TF-IDF（1-2gram，8000特征）+ 逻辑回归**，`class_weight=balanced`，准确率 ≈84% | `test_size=0.2` |
| `aspect_sentiment_matrix(df)` | **$5\times3$ 维度-情感矩阵**（Food/Service/Ambiance/Price/Location × 正/中/负） | — |
| `build_bert_dataset(df)` | 导出 BERT 三分类数据集（JSONL） | — |
| `build_absa_dataset(df)` | 导出细粒度 ABSA 数据集（PyABSA 格式） | — |

### 运营策略层

| 组件 | 功能 |
|---|---|
| `AlertSystem` | P0–P3 分级差评预警：1/3/7/14 日滚动窗口，差评率 ≥50%/35%/25%/20% 分级响应 |
| `ReportGenerator` | 一键导出 Excel（多 Sheet）/ Markdown 综合运营报告 |

---

## 主要实验结果

| 分析维度 | 关键发现 |
|---|---|
| 评分分布 | J 型分布，5 星占 52%，中性 3 星最少，正负比约 3.2:1 |
| Wilson 排名 | rank_drift > 10 的餐厅占 8%，系高评论量但质量存疑的争议区 |
| 餐厅聚类 | Premium 10% · Good 25% · Average 43% · At Risk 22%，At Risk 层差评率超阈值 |
| 时序规律 | 晚餐峰（18–22 时）占全日 38%，夏季（6–8 月）评论量高于均值 6–10% |
| STL 分解 | 2020 年 3–6 月残差异常最大，疫情冲击被残差分量成功隔离 |
| KMeans RFM | Champions+Loyal 约 30%，At Risk 流失识别率较规则方法提升 1.6 pp |
| LDA 主题 | 等待（T4）负面占比 52%，是单一可改进因素中差评率最高的来源 |
| 情感分类 | TF-IDF+LR 整体准确率 **82.3%**，正面 F1≈0.90，中性 F1≈0.45 |
| 维度矩阵 | Service 差评率最高（27%）、Food 正面率最高（76%） |

---

## 可视化图表（`outputs/figures/`）

运行 `python analysis/generate_figures.py` 后生成以下 9 张图：

| 文件 | 内容 |
|---|---|
| `fig_rating_distribution.pdf` | 评分 J 型分布直方图 |
| `fig_ranking_comparison.pdf` | Wilson vs 贝叶斯排名散点 + 漂移分布 |
| `fig_restaurant_clusters.pdf` | KMeans 聚类散点 + 各群规模柱图 |
| `fig_hourly_pattern.pdf` | 24 小时评论量双峰柱图 |
| `fig_stl_decomposition.pdf` | STL 四面板分解（含 COVID 标注） |
| `fig_rfm_clustering.pdf` | KMeans RFM 散点 + 用户规模柱图 |
| `fig_lda_topics.pdf` | LDA 8 主题比例水平条形图 |
| `fig_classifier_metrics.pdf` | TF-IDF+LR 精确率/召回率/F1 |
| `fig_aspect_sentiment.pdf` | 维度-情感 5×3 热力图 |

---

## 依赖

```
pandas>=2.0.0          # 数据处理
numpy>=1.24.0          # 数值计算
scikit-learn>=1.3.0    # KMeans / TF-IDF / LDA / LogisticRegression
statsmodels>=0.14.0    # STL 趋势分解
matplotlib>=3.7.0      # 可视化
seaborn>=0.12.0        # 热力图
openpyxl>=3.1.0        # Excel 导出
jieba>=0.42.1          # 中文分词（兼容旧数据）
jupyter>=1.0.0         # Notebook
datasets>=2.14.0       # HuggingFace 数据集加载
huggingface-hub>=0.19.0
```

---

## 引用

本项目学术报告引用了以下核心文献：

- Wilson (1927) — Score confidence interval
- Cleveland et al. (1990) — STL decomposition
- Blei et al. (2003) — LDA topic modeling
- Fader, Hardie & Lee (2005) — RFM/CLV framework
- Devlin et al. (2019) — BERT
- Pedregosa et al. (2011) — scikit-learn

完整参考文献见 [`report/yelp_analysis_report.tex`](report/yelp_analysis_report.tex)。

---

## License

MIT License © 2026 王岩方（2023111348）

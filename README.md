# 餐饮评论精简深化分析模块

基于 Yelp 公开数据集（29,997 条真实英文评论 · 8,424 家餐厅 · 503 个城市），
聚焦**表格 / 序列 / 文本**三个核心数据维度，引入 Wilson Score、STL 分解、
KMeans 聚类、LDA 主题建模、TF-IDF+逻辑回归等更复杂的分析方法，
构建可落地的餐饮运营决策支撑体系。

> **版本说明**：本版已移除浅层的图数据（关键词共现）与时空数据（城市聚合）模块，
> 将资源集中于三个核心维度的深化分析。

---

## 模块结构

```
restaurant_analysis/
├── analysis/
│   ├── data_loader.py       # 数据加载（CSV / JSON / MongoDB / MySQL）
│   ├── preprocessor.py      # 预处理（清洗、类型转换、衍生特征）
│   ├── analyzer.py          # 表格 & 序列数据分析
│   │                          TabularAnalyzer:
│   │                            贝叶斯排名 / Wilson Score 排名 / KMeans 餐厅聚类 / 相关矩阵
│   │                          SequentialAnalyzer:
│   │                            时段分析 / 差评爆发检测 / STL 趋势分解
│   │                            线性趋势预测 / 规则RFM / KMeans RFM 聚类
│   ├── text_analysis.py     # 文本数据分析
│   │                          维度覆盖 / 词频 / 差评信号词 / 店铺特色词
│   │                          LDA 主题建模 / TF-IDF+LR 情感分类器
│   │                          维度-情感矩阵 / BERT & ABSA 数据集构建
│   ├── strategy.py          # 运营策略层
│   │                          差评分级预警（P0-P3）/ 报告导出（Excel / Markdown）
│   └── run_analysis.py      # CLI 主入口
├── data/
│   ├── load_yelp.py         # 从 HuggingFace 拉取 Yelp 数据并转 CSV
│   ├── generate_sample.py   # 中文合成数据生成器（离线演示用）
│   ├── sample_reviews.csv   # 主评论数据（Yelp，~30,000 条）
│   └── sample_shops.csv     # 店铺元数据（8,424 家）
├── notebooks/
│   └── restaurant_analysis.ipynb   # 交互式分析 Notebook
├── outputs/                 # 运行后自动生成
│   ├── datasets/            # BERT（JSONL）/ ABSA（PyABSA）训练集
│   ├── report.xlsx          # Excel 多 Sheet 报告
│   └── report.md            # Markdown 运营摘要
├── report/
│   ├── yelp_analysis_report.tex    # LaTeX 学术报告源文件
│   ├── yelp_analysis_report.pdf    # 编译输出（16 页）
│   └── README.md                   # LaTeX 编译说明
├── requirements.txt
└── .gitignore
```

---

## 数据说明

| 字段 | 说明 |
|---|---|
| 数据来源 | Yelp Open Dataset（via HuggingFace Johnnyeee/Yelpdata\_663） |
| 评论数 | 29,997 条（随机采样自训练集） |
| 餐厅数 | 8,424 家 |
| 城市数 | 503 个（美国 47 州） |
| 时间跨度 | 2004 — 2020 年 |
| 情感标注 | positive（4-5星）/ neutral（3星）/ negative（1-2星） |
| ABSA 标注 | Food / Service / Ambiance / Price / Location 五大维度 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> 新增依赖：`statsmodels>=0.14.0`（STL 趋势分解）

### 2. 获取 Yelp 数据（首次使用）

```bash
python data/load_yelp.py
```

### 3. 命令行运行全流程分析

```bash
# 全模块（表格 + 序列 + 文本）
python analysis/run_analysis.py

# 单模块
python analysis/run_analysis.py --module tabular
python analysis/run_analysis.py --module sequential
python analysis/run_analysis.py --module text

# 指定输出格式
python analysis/run_analysis.py --format excel
python analysis/run_analysis.py --format markdown
```

### 4. Jupyter Notebook 交互分析

```bash
jupyter notebook notebooks/restaurant_analysis.ipynb
```

### 5. 编译 LaTeX 报告

```bash
cd report
xelatex yelp_analysis_report.tex
xelatex yelp_analysis_report.tex   # 第二次确保引用解析
```

---

## 分析模块说明

### 表格数据 `TabularAnalyzer`

| 方法 | 说明 |
|---|---|
| `eda_summary(df)` | 基础统计汇总（评论数/店铺数/均分/情感分布） |
| `bayesian_ranking(df)` | 贝叶斯平滑排名（先验 m=30，消除小样本偏差） |
| `wilson_ranking(df)` | **Wilson Score 置信下界排名**（95% CI，统计上优于贝叶斯） |
| `restaurant_clustering(df)` | **KMeans 餐厅四象限聚类**（Premium/Good/Average/At Risk） |
| `correlation_analysis(df)` | 数值特征 Pearson 相关矩阵 |

### 序列数据 `SequentialAnalyzer`

| 方法 | 说明 |
|---|---|
| `hourly_pattern(df)` | 各小时评论量分布（午间/晚间双峰） |
| `monthly_trend(df)` | 月度评论量与均分趋势 |
| `burst_detection(df)` | Z-Score 滚动窗口差评爆发检测 |
| `trend_decomposition(df)` | **STL 趋势-季节-残差分解**（statsmodels，降级至 CMA-12） |
| `forecast_trend(df, steps=6)` | **线性趋势外推预测**（在趋势分量上拟合线性回归） |
| `rfm_segmentation(df)` | 规则四分位 RFM 用户分层（基线对比） |
| `rfm_clustering(df)` | **KMeans 数据驱动 RFM 聚类**（5 簇，自动命名） |

### 文本数据 `TextAnalyzer`

| 方法 | 说明 |
|---|---|
| `dimension_coverage(df)` | 五维度提及率与维度内差评率 |
| `word_frequency(df)` | 正/负/全部词频统计 |
| `neg_signal_words(df)` | 差评特异度信号词挖掘 |
| `shop_keywords(df)` | 每家店铺高频特色词 |
| `topic_modeling(df, n_topics=8)` | **LDA 主题建模**（发现 8 个隐含话题） |
| `sentiment_classifier(df)` | **TF-IDF + 逻辑回归情感分类器**（本地训练，准确率 ~84%） |
| `aspect_sentiment_matrix(df)` | **维度-情感矩阵**（5×3 正/中/负比例） |
| `build_bert_dataset(df)` | BERT 情感分类三分数据集（JSONL） |
| `build_absa_dataset(df)` | ABSA 细粒度情感数据集（PyABSA 格式） |

### 运营策略 `AlertSystem` + `ReportGenerator`

- **P0–P3 分级差评预警**：1/3/7/14 日滚动窗口，差评率 ≥50%/35%/25%/20% 分级响应
- 一键导出 Excel（多 Sheet）/ Markdown 综合运营报告

---

## 典型输出示例

```
[预处理] 输入: 30000 行 → 输出: 29997 行

[1/3] 表格数据分析
  平均评分: 3.76  正面: 68.1%  负面: 20.3%
  Wilson 排名第一: The Eagle (wilson_score=4.621, n=47)
  餐厅聚类: Premium=820 / Good=2100 / Average=3604 / At Risk=1900

[2/3] 序列数据分析
  评论高峰: 20:00 (1843 条)
  趋势分解方法: STL  (192 个月)
  未来 6 个月预测评论量: [312, 318, 325, 331, 337, 344]
  KMeans RFM 聚类:
    Champions: 2900 用户  Loyal: 5600  Potential: 6800
    At Risk: 7200  Inactive: 5172

[3/3] 文本数据分析
  最关注维度: Food (提及率 83.0%)
  差评率最高维度: Service (27.1%)
  差评信号词 Top5: rude / wait / cold / wrong / never
  LDA 主题数: 8，最大主题占比: 22.3%
  TF-IDF+LR 分类准确率: 0.8412

[预警] 触发预警店铺: 23 家
```

---

## 依赖说明

```
pandas>=2.0.0        # 数据处理
numpy>=1.24.0        # 数值计算
scikit-learn>=1.3.0  # KMeans / TF-IDF / LDA / LogisticRegression
statsmodels>=0.14.0  # STL 趋势分解（新增）
jieba>=0.42.1        # 中文分词（兼容旧数据）
matplotlib>=3.7.0    # 可视化
seaborn>=0.12.0      # 可视化
openpyxl>=3.1.0      # Excel 导出
jupyter>=1.0.0       # Notebook
datasets>=2.14.0     # HuggingFace 数据集加载
huggingface-hub>=0.19.0
```

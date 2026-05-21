# 餐饮评论多数据类型分析模块

基于 1000 条真实感餐饮评论数据，覆盖六类数据处理方法，并落地到餐饮运营策略。

---

## 模块结构

```
restaurant_analysis/
├── analysis/
│   ├── data_loader.py      # 数据加载（CSV / JSON / MongoDB / MySQL）
│   ├── preprocessor.py     # 数据预处理（清洗、类型转换、特征派生）
│   ├── analyzer.py         # 四类数据分析
│   │                         Part 3-① 表格数据：EDA + 贝叶斯店铺排名
│   │                         Part 3-② 序列数据：时段分析 + RFM 用户分层
│   │                         Part 3-③ 图数据：菜品共现 + KOL 识别
│   │                         Part 4-① 时空数据：城市热力 + 选址评分
│   ├── text_analysis.py    # Part 4-② 非结构化文本数据
│   │                         关键词提取 / 差评信号词 / BERT & ABSA 数据集构建
│   ├── strategy.py         # 运营策略层
│   │                         差评分级预警（P0-P3）/ 综合运营报告导出
│   └── run_analysis.py     # CLI 主入口
├── data/
│   ├── generate_sample.py  # 数据生成器（20家店铺 × 85条模板 → 1000条）
│   ├── sample_reviews.csv  # 评论样本数据
│   └── sample_shops.csv    # 店铺样本数据
├── notebooks/
│   └── restaurant_analysis.ipynb  # 交互式分析 Notebook
├── outputs/                # 运行后自动生成
│   ├── figures/            # 可视化图表（12张）
│   ├── datasets/           # BERT / ABSA 训练集
│   ├── report.json         # 结构化报告
│   ├── report.xlsx         # Excel 多 Sheet 报告
│   └── report.md           # Markdown 运营报告
├── requirements.txt
└── .gitignore
```

---

## 数据说明

| 字段 | 说明 |
|---|---|
| 评论数 | 1000 条 |
| 店铺数 | 20 家（北京/上海/成都/广州/深圳/杭州 6 城市）|
| 菜系 | 火锅/川菜/粤菜/日料/面食/烤鸭/海鲜/杭帮菜 |
| 情感标注 | positive / neutral / negative |
| ABSA 标注 | 口味/环境/服务/价格/食材五大维度 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 生成/更新样本数据（可选）

```bash
python data/generate_sample.py
```

### 3. 命令行运行全流程分析

```bash
# 全模块
python analysis/run_analysis.py

# 单模块
python analysis/run_analysis.py --module tabular
python analysis/run_analysis.py --module sequential
python analysis/run_analysis.py --module graph
python analysis/run_analysis.py --module geo
python analysis/run_analysis.py --module text

# 指定输出格式
python analysis/run_analysis.py --format excel
```

### 4. Jupyter Notebook 交互分析

```bash
jupyter notebook notebooks/restaurant_analysis.ipynb
```

---

## 分析模块说明

### Part 3-① 表格数据 `TabularAnalyzer`

- 评分分布、情感分布、消费类型对比
- **贝叶斯平滑**店铺综合排名（消除小样本偏差）
- 数值特征相关性热力图

### Part 3-② 序列数据 `SequentialAnalyzer`

- 各小时/星期评论量与差评率分析
- **Z-Score 差评爆发检测**（异常时间点识别）
- **RFM 用户分层**：高价值活跃 / 普通活跃 / 沉睡用户 / 流失风险 / 已流失

### Part 3-③ 图数据 `GraphAnalyzer`

- 菜品情感得分（正评率 vs 负评率）
- **菜品共现矩阵**（推荐套餐搭配）
- **KOL 高影响力用户识别**（影响力评分模型）

### Part 4-① 时空数据 `SpatiotemporalAnalyzer`

- 城市维度评论量、评分、差评率对比
- 城市 × 时段**评论热力矩阵**
- **选址综合评分**（评分 + 市场活跃度 + 差评率）

### Part 4-② 文本数据 `TextAnalyzer`

- 口味/环境/服务/价格/食材**五维度覆盖率**
- 正/负评论**高频词对比**
- **差评信号词**提取（差评特有度排序）
- **BERT 情感分类**训练集（train/val/test 三段式 JSONL）
- **ABSA 细粒度情感**数据集（PyABSA 标准格式）

### 运营策略 `AlertSystem` + `ReportGenerator`

- **P0-P3 分级差评预警**（1日/3日/7日/14日滚动窗口）
- 自动生成可执行运营建议
- 一键导出 JSON / Excel / Markdown 综合运营报告

---

## 输出示例

```
[1/5] 表格数据分析
  总评论: 1000  均分: 3.83  店铺: 20
  排名第一: 大壶春生煎（云南路店）(综合分 0.929)

[2/5] 序列数据分析
  评论高峰: 14:00 (高峰：增派人手)
  用户分层: {高价值活跃: 12, 普通活跃: -, 沉睡用户: 19, ...}

[3/5] 图数据分析
  最高频菜品: 西湖醋鱼 (提及94次, 正评60%)
  KOL用户: 15 人

[4/5] 时空数据分析
  最活跃城市: 上海 (233条)  最佳选址评级: A优选

[5/5] 文本数据分析
  最关注维度: 口味 (提及率 86.1%)
  差评信号词: 服务员 / 新鲜 / 一般 / 海鲜
  BERT: train=700 val=150 test=150
  ABSA: 3004 条 aspect 样本
```

# 报告编译说明

## 编译环境要求

- TeX 发行版：**TeX Live 2022+** 或 **MiKTeX**（Windows 推荐）
- 编译引擎：**XeLaTeX**（支持中文）
- 中文字体：SimSun / SimHei / KaiTi / Microsoft YaHei（Windows 系统自带）

## 编译步骤

```bash
# 在 report/ 目录下执行，完整编译 4 次（含参考文献）
xelatex yelp_analysis_report.tex
bibtex  yelp_analysis_report
xelatex yelp_analysis_report.tex
xelatex yelp_analysis_report.tex
```

## 快速编译（不含参考文献编号）

```bash
xelatex yelp_analysis_report.tex
```

## VSCode / Cursor 一键编译

安装 LaTeX Workshop 插件后，在 `.tex` 文件中按 `Ctrl+Alt+B` 即可自动编译。

## 报告结构（精简深化版）

| 章节 | 内容 |
|---|---|
| 1 引言 | 精简动机、核心研究问题、数据集说明 |
| 2 数据预处理 | 字段标准化、J 型分布、基础统计 |
| 3 表格数据分析 | Wilson Score 排名、KMeans 餐厅聚类、相关矩阵 |
| 4 序列数据分析 | STL 趋势分解、线性预测、KMeans RFM 用户聚类 |
| 5 文本数据分析 | LDA 主题建模、TF-IDF+LR 情感分类器、维度-情感矩阵 |
| 6 运营策略 | P0-P3 差评预警、跨模块行动矩阵 |
| 7 结论 | 六条核心发现与研究局限 |
| 参考材料 | 11 条经核实的学术引文与数据来源 |

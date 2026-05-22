# -*- coding: utf-8 -*-
"""
分析主入口（已对齐当前 API，移除图数据/时空数据模块）
用法:
  python analysis/run_analysis.py                          # 全流程
  python analysis/run_analysis.py --module tabular         # 单模块
  python analysis/run_analysis.py --module sequential
  python analysis/run_analysis.py --module text
  python analysis/run_analysis.py --format excel
"""

import os
import sys
import argparse

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.data_loader import ReviewDataLoader
from analysis.preprocessor import ReviewPreprocessor
from analysis.analyzer import TabularAnalyzer, SequentialAnalyzer
from analysis.text_analysis import TextAnalyzer
from analysis.strategy import AlertSystem, ReportGenerator


def main():
    parser = argparse.ArgumentParser(description="Yelp 餐饮评论分析流水线")
    parser.add_argument("--input",  default="data/sample_reviews.csv")
    parser.add_argument("--module", default="all",
                        choices=["all", "tabular", "sequential", "text", "strategy"])
    parser.add_argument("--format", default="all",
                        choices=["excel", "markdown", "all"])
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(os.path.join(args.output, "datasets"), exist_ok=True)

    # ── 加载 & 预处理 ────────────────────────────────────────
    print(f"[0/3] 加载数据: {args.input}")
    df_raw = ReviewDataLoader.load(args.input)
    ReviewDataLoader.describe(df_raw)

    print("\n[预处理] 开始...")
    df = ReviewPreprocessor().fit_transform(df_raw)

    run_all    = (args.module == "all")
    report_data: dict = {}

    # ── Part 3-① 表格数据 ───────────────────────────────────
    if run_all or args.module == "tabular":
        print("\n[1/3] 表格数据分析")
        ta = TabularAnalyzer()

        eda = ta.eda_summary(df)
        print(eda.to_string(index=False))

        corr = ta.correlation_analysis(df)
        print(f"  评分↔情感相关: {corr.loc['review_score','sentiment_label']:.3f}")

        wilson = ta.wilson_ranking(df, min_reviews=5)
        top1   = wilson.iloc[0]
        print(f"  Wilson 排名第一: {top1['shop_name']}  "
              f"(wilson_score={top1['wilson_score']}, n={top1['review_count']})")

        detail, cluster_summary = ta.restaurant_clustering(df, n_clusters=4)
        print(f"  餐厅聚类汇总:\n{cluster_summary.to_string(index=False)}")

        report_data["eda"]             = eda
        report_data["wilson_ranking"]  = wilson.head(50)
        report_data["cluster_detail"]  = detail
        report_data["cluster_summary"] = cluster_summary
        report_data["correlation"]     = corr.reset_index()

    # ── Part 3-② 序列数据 ───────────────────────────────────
    if run_all or args.module == "sequential":
        print("\n[2/3] 序列数据分析")
        sa = SequentialAnalyzer()

        hourly = sa.hourly_pattern(df)
        peak   = hourly.loc[hourly["count"].idxmax()]
        print(f"  评论高峰: {int(peak['review_hour'])}:00 ({int(peak['count'])} 条)")

        burst = sa.burst_detection(df)
        alert_days = burst["alert"].sum()
        print(f"  差评爆发日: {alert_days} 天")

        decomp = sa.trend_decomposition(df)
        print(f"  趋势分解方法: {decomp['method'].iloc[0]}  "
              f"({len(decomp)} 个月)")

        forecast = sa.forecast_trend(df, steps=6)
        fc_rows  = forecast[forecast["type"] == "forecast"]
        if not fc_rows.empty:
            print(f"  未来 6 个月预测评论量: "
                  f"{fc_rows['count'].tolist()}")

        rfm_detail, rfm_km_summary = sa.rfm_clustering(df, n_clusters=5)
        rfm_rule = sa.rfm_segmentation(df)
        print(f"  KMeans RFM 聚类:\n{rfm_km_summary.to_string(index=False)}")

        report_data["hourly"]          = hourly
        report_data["burst"]           = burst[burst["alert"]]
        report_data["trend_decomp"]    = decomp
        report_data["forecast"]        = forecast
        report_data["rfm_km_detail"]   = rfm_detail
        report_data["rfm_km_summary"]  = rfm_km_summary
        report_data["rfm_rule"]        = rfm_rule

    # ── Part 4-② 文本数据 ───────────────────────────────────
    if run_all or args.module == "text":
        print("\n[3/3] 文本数据分析")
        txt = TextAnalyzer()

        dim_cov = txt.dimension_coverage(df)
        print(f"  维度覆盖率 Top1: "
              f"{dim_cov.iloc[0]['dimension']} "
              f"({dim_cov.iloc[0]['mention%']}%)")

        asp_mat = txt.aspect_sentiment_matrix(df)
        worst = asp_mat.sort_values("negative_pct", ascending=False).iloc[0]
        print(f"  差评率最高维度: {worst['dimension']} ({worst['negative_pct']}%)")

        neg_words = txt.neg_signal_words(df)
        top5 = " / ".join(neg_words["word"].head(5).tolist()
                          if "word" in neg_words.columns
                          else neg_words.iloc[:, 0].head(5).tolist())
        print(f"  差评信号词 Top5: {top5}")

        topics = txt.topic_modeling(df, n_topics=8)
        print(f"  LDA 主题数: {len(topics)}，"
              f"最大主题占比: {topics['proportion'].max()}%")

        clf_result = txt.sentiment_classifier(df)
        print(f"  TF-IDF+LR 分类准确率: {clf_result['accuracy']:.4f}")

        bert_ds = txt.build_bert_dataset(df)
        absa_ds = txt.build_absa_dataset(df)
        txt.save_bert_dataset(bert_ds, os.path.join(args.output, "datasets"))
        if not absa_ds.empty:
            txt.save_absa_pyabsa(
                absa_ds,
                os.path.join(args.output, "datasets", "absa_train.txt")
            )

        report_data["dim_coverage"]   = dim_cov
        report_data["aspect_matrix"]  = asp_mat
        report_data["neg_signals"]    = neg_words.head(15)
        report_data["topics"]         = topics
        report_data["classifier_acc"] = pd.DataFrame(
            [{"metric": k, "value": v}
             for k, v in clf_result["report"].items()
             if isinstance(v, (int, float))]
        )

    # ── 差评预警 & 报告 ──────────────────────────────────────
    print("\n[预警] 扫描差评...")
    alerts = AlertSystem().run(df)
    print(f"  触发预警店铺: {len(alerts)} 家")
    report_data["alerts"] = alerts

    gen = ReportGenerator(output_dir=args.output)
    if args.format in ("excel", "all"):
        gen.to_excel(report_data)
    if args.format in ("markdown", "all"):
        gen.to_markdown(report_data)

    print(f"\n完成！输出目录: {args.output}/")


if __name__ == "__main__":
    main()

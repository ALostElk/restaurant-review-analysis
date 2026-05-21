# -*- coding: utf-8 -*-
"""
分析主入口
用法:
  python analysis/run_analysis.py                          # 全流程
  python analysis/run_analysis.py --module tabular         # 单模块
  python analysis/run_analysis.py --format excel           # 指定输出格式
"""

import os, sys, argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.data_loader import ReviewDataLoader
from analysis.preprocessor import ReviewPreprocessor
from analysis.analyzer import TabularAnalyzer, SequentialAnalyzer, GraphAnalyzer, SpatiotemporalAnalyzer
from analysis.text_analysis import TextAnalyzer
from analysis.strategy import AlertSystem, ReportGenerator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="data/sample_reviews.csv")
    parser.add_argument("--module", default="all",
                        choices=["all","tabular","sequential","graph","geo","text","strategy"])
    parser.add_argument("--format", default="all", choices=["json","excel","markdown","all"])
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    os.makedirs(os.path.join(args.output, "figures"), exist_ok=True)
    os.makedirs(os.path.join(args.output, "datasets"), exist_ok=True)

    # ── 加载 & 预处理 ────────────────────────────────────────
    print(f"加载数据: {args.input}")
    df_raw = ReviewDataLoader.load(args.input)
    ReviewDataLoader.describe(df_raw)

    print("\n预处理中...")
    df = ReviewPreprocessor().fit_transform(df_raw)

    run_all = (args.module == "all")
    report_data = {}

    # ── 表格数据 ─────────────────────────────────────────────
    if run_all or args.module == "tabular":
        print("\n[1/5] 表格数据分析")
        ta = TabularAnalyzer(df)
        stats   = ta.basic_stats()
        ranking = ta.shop_ranking()
        print(f"  总评论: {stats['总评论数']}  均分: {stats['平均评分']}  店铺: {stats['店铺数']}")
        print(f"  排名第一: {ranking.iloc[0]['shop_name']} (综合分 {ranking.iloc[0]['综合分']})")
        report_data["shop_ranking"]   = ranking.to_dict(orient="records")
        report_data["score_dist"]     = ta.score_distribution().to_dict(orient="records")
        report_data["order_type"]     = ta.order_type_stats().to_dict(orient="records")
        report_data["correlation"]    = ta.correlation_matrix().to_dict()

    # ── 序列数据 ─────────────────────────────────────────────
    if run_all or args.module == "sequential":
        print("\n[2/5] 序列数据分析")
        sa = SequentialAnalyzer(df)
        hourly = sa.hourly_stats()
        peak   = hourly.loc[hourly["评论数"].idxmax()]
        burst  = sa.detect_burst()
        crisis = burst[burst["风险"].isin(["危机","预警"])]
        rfm    = sa.rfm_segments()
        seg_ct = rfm["用户类型"].value_counts().to_dict()
        print(f"  评论高峰: {int(peak['小时'])}:00  ({peak['建议']})")
        print(f"  差评爆发异常点: {len(crisis)} 个")
        print(f"  用户分层: {seg_ct}")
        report_data["hourly_stats"]   = hourly.to_dict(orient="records")
        report_data["rfm_segments"]   = rfm.to_dict(orient="records")

    # ── 图数据 ───────────────────────────────────────────────
    if run_all or args.module == "graph":
        print("\n[3/5] 图数据分析")
        ga = GraphAnalyzer(df)
        dish_sent = ga.dish_sentiment()
        cooccur   = ga.dish_cooccurrence()
        kol       = ga.influencer_users()
        if not dish_sent.empty:
            top = dish_sent.iloc[0]
            print(f"  最高频菜品: {top['菜品']} (提及{int(top['提及次数'])}次, 正评{top['正评率%']:.0f}%)")
        print(f"  菜品共现对数: {len(cooccur)}  KOL用户: {len(kol)} 人")
        report_data["dish_sentiment"] = dish_sent.head(15).to_dict(orient="records")
        report_data["dish_cooccur"]   = cooccur.head(15).to_dict(orient="records")
        report_data["kol_users"]      = kol.to_dict(orient="records")

    # ── 时空数据 ─────────────────────────────────────────────
    if run_all or args.module == "geo":
        print("\n[4/5] 时空数据分析")
        geo = SpatiotemporalAnalyzer(df)
        city_sum = geo.city_summary()
        site     = geo.site_score()
        if not city_sum.empty:
            top_city = city_sum.iloc[0]
            print(f"  最活跃城市: {top_city['city']} ({int(top_city['评论数'])} 条)")
        if not site.empty:
            print(f"  最佳选址: {site.iloc[0]['city']} (评级 {site.iloc[0]['评级']})")
        report_data["city_summary"] = city_sum.to_dict(orient="records")
        report_data["site_score"]   = site.to_dict(orient="records")

    # ── 文本数据 ─────────────────────────────────────────────
    if run_all or args.module == "text":
        print("\n[5/5] 文本数据分析")
        txt = TextAnalyzer()
        dim_cov    = txt.dimension_coverage(df)
        neg_words  = txt.neg_signal_words(df)
        bert_ds    = txt.build_bert_dataset(df)
        absa_ds    = txt.build_absa_dataset(df)
        top_dim    = dim_cov.iloc[0] if not dim_cov.empty else None
        if top_dim is not None:
            print(f"  最关注维度: {top_dim['维度']} (提及率 {top_dim['提及率%']}%)")
        neg_top5 = " / ".join(neg_words["词语"].head(5).tolist()) if not neg_words.empty else "-"
        print(f"  差评信号词: {neg_top5}")
        txt.save_bert_dataset(bert_ds, os.path.join(args.output, "datasets"))
        if not absa_ds.empty:
            txt.save_absa_pyabsa(absa_ds, os.path.join(args.output, "datasets", "absa_train.txt"))
        report_data["dim_coverage"] = dim_cov.to_dict(orient="records")
        report_data["neg_signals"]  = neg_words.head(15).to_dict(orient="records")

    # ── 预警 & 报告 ──────────────────────────────────────────
    print("\n生成运营报告...")
    alert = AlertSystem(df)
    alert_df = alert.generate()
    warn_ct  = (alert_df["预警等级"] != "正常").sum() if not alert_df.empty else 0
    print(f"  预警店铺: {warn_ct} 家")
    report_data["alert_text"] = alert.text_report()

    gen = ReportGenerator(output_dir=args.output)
    report = gen.build(df, report_data)

    if args.format in ("json", "all"):    gen.to_json(report)
    if args.format in ("excel", "all"):   gen.to_excel(report)
    if args.format in ("markdown", "all"):gen.to_markdown(report)

    print(f"\n全部完成！输出目录: {args.output}/")


if __name__ == "__main__":
    main()

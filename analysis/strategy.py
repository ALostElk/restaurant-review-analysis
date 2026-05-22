# -*- coding: utf-8 -*-
"""
运营策略模块
差评预警（P0-P3分级）+ 综合运营报告（Excel / Markdown）
无状态接口: AlertSystem().run(df)  /  ReportGenerator(out).to_excel(results)
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np


class AlertSystem:
    """差评分级预警（无状态，run(df) 直接调用）"""

    LEVELS = [
        ("P0", 1,  0.50, "P0-Crisis"),
        ("P1", 3,  0.35, "P1-Warning"),
        ("P2", 7,  0.25, "P2-Watch"),
        ("P3", 14, 0.20, "P3-Track"),
    ]
    ACTIONS = {
        "P0": "Immediate escalation: contact customers, halt new orders",
        "P1": "Reply all negative reviews within 24h, issue vouchers",
        "P2": "Analyze root causes this week, optimize service process",
        "P3": "Monitor daily trend, benchmark against competitors",
    }

    def run(self, df: pd.DataFrame) -> list:
        """
        扫描所有店铺，返回触发预警的列表
        每条: {level, shop_id, shop_name, score, message}
        """
        df = df.copy()
        df["review_time"]     = pd.to_datetime(df.get("review_time"), errors="coerce")
        df["sentiment_label"] = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce")
        df["review_score"]    = pd.to_numeric(df.get("review_score", 3),    errors="coerce")
        ref = df["review_time"].dropna().max()
        if pd.isna(ref):
            return []

        alerts = []
        for shop_id, sdf in df.groupby("shop_id"):
            sdf = sdf.dropna(subset=["review_time"])
            if len(sdf) < 3:
                continue
            shop_name = sdf["shop_name"].iloc[0] if "shop_name" in sdf.columns else str(shop_id)

            triggered = None
            neg_rate   = 0.0
            for level, days, threshold, label in self.LEVELS:
                window = sdf[sdf["review_time"] >= ref - timedelta(days=days)]
                if len(window) < 2:
                    continue
                rate = (window["sentiment_label"] == -1).mean()
                if rate >= threshold:
                    triggered = (level, label, days, rate)
                    neg_rate  = rate
                    break

            if triggered:
                level, label, days, rate = triggered
                alerts.append({
                    "level":     label,
                    "shop_id":   shop_id,
                    "shop_name": shop_name,
                    "score":     round(sdf["review_score"].mean(), 2),
                    "neg_rate":  round(rate * 100, 1),
                    "message":   f"{days}d negative rate {rate*100:.0f}% >= threshold",
                    "action":    self.ACTIONS.get(level, "Monitor"),
                })

        # 按严重程度排序
        order = {"P0-Crisis": 0, "P1-Warning": 1, "P2-Watch": 2, "P3-Track": 3}
        alerts.sort(key=lambda x: order.get(x["level"], 9))
        return alerts


class ReportGenerator:
    """综合报告生成器（Excel + Markdown）"""

    def __init__(self, output_dir: str = "outputs"):
        self.out = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def to_excel(self, results: dict, name: str = "report.xlsx") -> str:
        """将各模块 DataFrame 写入 Excel 多 Sheet"""
        path = os.path.join(self.out, name)
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                for key, val in results.items():
                    if isinstance(val, pd.DataFrame) and not val.empty:
                        sheet = key[:31]
                        val.to_excel(writer, sheet_name=sheet, index=False)
                    elif isinstance(val, list) and val:
                        pd.DataFrame(val).to_excel(
                            writer, sheet_name=key[:31], index=False)
            print(f"[报告] Excel -> {path}")
        except Exception as e:
            print(f"[报告] Excel 失败: {e}")
        return path

    def to_markdown(self, results: dict, name: str = "report.md") -> str:
        """生成 Markdown 摘要报告"""
        path = os.path.join(self.out, name)
        lines = [
            "# Yelp Restaurant Analysis Report",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # 概览
        if "eda" in results and isinstance(results["eda"], pd.DataFrame):
            lines += ["## Overview", ""]
            for _, row in results["eda"].iterrows():
                lines.append(f"- **{row.get('指标', row.iloc[0])}**: {row.get('值', row.iloc[1])}")
            lines.append("")

        # 排名 Top 10
        if "ranking" in results and isinstance(results["ranking"], pd.DataFrame):
            rk = results["ranking"].head(10)
            if not rk.empty:
                lines += ["## Top 10 Restaurants (Bayesian)", ""]
                cols = ["shop_name", "city", "review_count", "avg_score", "bayes_score"]
                cols = [c for c in cols if c in rk.columns]
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for _, r in rk.iterrows():
                    lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
                lines.append("")

        # 预警
        if "alerts" in results:
            alerts = results["alerts"]
            if isinstance(alerts, pd.DataFrame):
                alerts = alerts.to_dict("records")
            if alerts:
                lines += ["## Alerts", ""]
                for a in alerts[:10]:
                    lines.append(f"- **[{a.get('level','')}]** {a.get('shop_name','')}: "
                                 f"{a.get('message','')} → {a.get('action','')}")
                lines.append("")

        content = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[报告] Markdown -> {path}")
        return path

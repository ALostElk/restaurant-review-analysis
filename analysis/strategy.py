# -*- coding: utf-8 -*-
"""
运营策略模块
差评预警（P0-P3分级）+ 综合运营报告（JSON / Excel / Markdown）
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np


class AlertSystem:
    """差评分级预警系统"""

    LEVELS = {
        "P0": {"days": 1,  "threshold": 0.50, "label": "P0 危机"},
        "P1": {"days": 3,  "threshold": 0.35, "label": "P1 预警"},
        "P2": {"days": 7,  "threshold": 0.25, "label": "P2 关注"},
        "P3": {"days": 14, "threshold": 0.20, "label": "P3 跟踪"},
    }
    ACTIONS = {
        "P0": ["立即召开紧急会议，排查当日问题", "主动联系差评用户道歉并补偿", "暂停接新单优先处理投诉"],
        "P1": ["24小时内回复所有差评", "回顾近3日客诉，找出集中问题点", "对差评用户发放定向优惠券"],
        "P2": ["本周内完成差评原因分析", "优化服务流程薄弱环节", "推出限时优惠活动提振口碑"],
        "P3": ["持续监控评分趋势（每日）", "与竞品对比找差距", "绩效与口碑指标挂钩"],
    }

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df["review_time"]    = pd.to_datetime(self.df.get("review_time"), errors="coerce")
        self.df["sentiment_label"] = pd.to_numeric(self.df.get("sentiment_label", 0), errors="coerce")
        self.df["review_score"]   = pd.to_numeric(self.df.get("review_score", 3), errors="coerce")
        self.ref = self.df["review_time"].max()

    def _neg_rate(self, shop_df: pd.DataFrame, days: int) -> float:
        w = shop_df[shop_df["review_time"] >= self.ref - timedelta(days=days)]
        return (w["sentiment_label"] == -1).mean() if len(w) else 0.0

    def generate(self) -> pd.DataFrame:
        rows = []
        for shop_id, sdf in self.df.groupby("shop_id"):
            sdf = sdf.dropna(subset=["review_time"])
            if len(sdf) < 3:
                continue
            shop_name = sdf["shop_name"].iloc[0] if "shop_name" in sdf.columns else shop_id
            rates = {lv: self._neg_rate(sdf, cfg["days"]) for lv, cfg in self.LEVELS.items()}

            level = None
            for lv, cfg in self.LEVELS.items():
                if rates[lv] >= cfg["threshold"]:
                    level = lv
                    break

            # 评分趋势
            sdf = sdf.sort_values("review_time")
            recent = sdf.tail(10)["review_score"].mean()
            prior  = sdf.head(max(len(sdf)-10,1))["review_score"].mean()
            trend  = "上升" if recent > prior + 0.2 else ("下降" if recent < prior - 0.2 else "平稳")

            rows.append({
                "预警等级":  self.LEVELS[level]["label"] if level else "正常",
                "shop_name": shop_name,
                "平均分":    round(sdf["review_score"].mean(), 2),
                "评分趋势":  trend,
                "1日差评%":  round(rates["P0"] * 100, 1),
                "3日差评%":  round(rates["P1"] * 100, 1),
                "7日差评%":  round(rates["P2"] * 100, 1),
                "7日评论数": int(len(sdf[sdf["review_time"] >= self.ref - timedelta(days=7)])),
                "整体差评%": round((sdf["sentiment_label"] == -1).mean() * 100, 1),
                "建议行动":  self.ACTIONS.get(level, ["持续监控"]),
                "_level_key": level,
            })

        result = pd.DataFrame(rows)
        if result.empty:
            return result
        order = {"P0":0,"P1":1,"P2":2,"P3":3,None:4}
        result["_sort"] = result["_level_key"].map(order)
        return result.sort_values(["_sort","7日差评%"], ascending=[True,False]).drop(columns=["_sort","_level_key"])

    def text_report(self) -> str:
        alerts = self.generate()
        lines = ["="*55, f"差评预警报告  {self.ref.strftime('%Y-%m-%d')}", "="*55]
        has_alert = False
        for _, r in alerts.iterrows():
            if r["预警等级"] == "正常":
                continue
            has_alert = True
            lines.append(f"\n[{r['预警等级']}]  {r['shop_name']}")
            lines.append(f"  平均分: {r['平均分']}  趋势: {r['评分趋势']}  7日差评率: {r['7日差评%']}%")
            lines.append("  建议:")
            for a in r["建议行动"]:
                lines.append(f"    - {a}")
        if not has_alert:
            lines.append("\n所有店铺运营正常，无需预警")
        return "\n".join(lines)


class ReportGenerator:
    """综合运营报告生成器"""

    def __init__(self, output_dir: str = "outputs"):
        self.out = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def build(self, df: pd.DataFrame, results: dict) -> dict:
        """汇总各模块结果为报告字典"""
        report = {
            "generated_at": datetime.now().isoformat()[:19],
            "overview": {
                "总评论数":  len(df),
                "店铺数":    df["shop_id"].nunique() if "shop_id" in df.columns else 0,
                "用户数":    df["user_id"].nunique() if "user_id" in df.columns else 0,
                "平台":      df["platform"].value_counts().to_dict() if "platform" in df.columns else {},
                "平均分":    round(pd.to_numeric(df.get("review_score"), errors="coerce").mean(), 2),
                "时间范围":  self._date_range(df),
            },
        }
        report.update(results)
        return report

    def to_json(self, report: dict, name: str = "report.json") -> str:
        path = os.path.join(self.out, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"[报告] JSON -> {path}")
        return path

    def to_excel(self, report: dict, name: str = "report.xlsx") -> str:
        path = os.path.join(self.out, name)
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame([report["overview"]]).to_excel(writer, sheet_name="概览", index=False)
                for key, val in report.items():
                    if isinstance(val, list) and val:
                        pd.DataFrame(val).to_excel(writer, sheet_name=key[:30], index=False)
                    elif isinstance(val, pd.DataFrame) and not val.empty:
                        val.to_excel(writer, sheet_name=key[:30], index=False)
            print(f"[报告] Excel -> {path}")
        except Exception as e:
            print(f"[报告] Excel 失败: {e}")
        return path

    def to_markdown(self, report: dict, name: str = "report.md") -> str:
        path = os.path.join(self.out, name)
        ov = report.get("overview", {})
        lines = [
            "# 餐饮评论运营分析报告",
            f"> 生成时间: {report.get('generated_at','')}",
            "",
            "## 一、数据概览",
            f"| 指标 | 值 |", "| --- | --- |",
            f"| 总评论数 | {ov.get('总评论数',0):,} |",
            f"| 覆盖店铺 | {ov.get('店铺数',0)} 家 |",
            f"| 覆盖用户 | {ov.get('用户数',0):,} 人 |",
            f"| 平均评分 | {ov.get('平均分','-')} |",
            f"| 时间范围 | {ov.get('时间范围','-')} |",
            "",
        ]
        if "shop_ranking" in report:
            lines += ["## 二、店铺综合排名", ""]
            rk = pd.DataFrame(report["shop_ranking"])
            if not rk.empty:
                lines.append("| 排名 | 店铺 | 评级 | 综合分 | 差评率% |")
                lines.append("| --- | --- | --- | --- | --- |")
                for _, r in rk.head(5).iterrows():
                    lines.append(f"| {r.get('排名','-')} | {r.get('shop_name','-')} | "
                                 f"{r.get('评级','-')} | {r.get('综合分','-')} | {r.get('差评率%','-')} |")
            lines.append("")
        if "alerts" in report:
            alert_text = report.get("alert_text", "")
            lines += ["## 三、差评预警", "```", alert_text, "```", ""]
        content = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[报告] Markdown -> {path}")
        return path

    @staticmethod
    def _date_range(df: pd.DataFrame) -> str:
        t = pd.to_datetime(df.get("review_time"), errors="coerce").dropna()
        return f"{t.min().strftime('%Y-%m-%d')} ~ {t.max().strftime('%Y-%m-%d')}" if not t.empty else "-"

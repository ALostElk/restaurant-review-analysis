# -*- coding: utf-8 -*-
"""
核心分析模块
覆盖：表格数据 / 序列数据 / 图数据 / 时空数据四类处理方法
"""

import json
import warnings
from collections import Counter
from datetime import timedelta
from itertools import combinations
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────
# Part 3-① 表格数据：EDA + 店铺综合排名
# ─────────────────────────────────────────────────────────────

class TabularAnalyzer:
    """表格数据分析：统计概览、评分分布、店铺排名"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        for col in ["review_score", "like_count", "reply_count", "sentiment_label",
                    "content_len", "taste_score", "environment_score", "service_score"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    # 基础统计
    def basic_stats(self) -> dict:
        df = self.df
        return {
            "总评论数":   len(df),
            "店铺数":     df["shop_id"].nunique() if "shop_id" in df.columns else 0,
            "用户数":     df["user_id"].nunique() if "user_id" in df.columns else 0,
            "平台分布":   df["platform"].value_counts().to_dict() if "platform" in df.columns else {},
            "平均评分":   round(df["review_score"].mean(), 2) if "review_score" in df.columns else None,
            "带图比例%":  round(df["has_image"].mean() * 100, 1) if "has_image" in df.columns else None,
            "情感分布":   df["sentiment"].value_counts().to_dict() if "sentiment" in df.columns else {},
        }

    # 评分分布
    def score_distribution(self) -> pd.DataFrame:
        if "review_score" not in self.df.columns:
            return pd.DataFrame()
        vc = self.df["review_score"].round().astype("Int64").value_counts().sort_index()
        return pd.DataFrame({"星级": vc.index, "评论数": vc.values,
                              "占比%": (vc.values / len(self.df) * 100).round(1)})

    # 消费类型对比
    def order_type_stats(self) -> pd.DataFrame:
        if "order_type" not in self.df.columns:
            return pd.DataFrame()
        grp = self.df[self.df["order_type"].fillna("").str.strip() != ""].groupby("order_type").agg(
            评论数 = ("review_id", "count"),
            平均分 = ("review_score", "mean"),
            差评率 = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean() * 100),
        ).reset_index().rename(columns={"差评率": "差评率%"}).round(2)
        return grp.sort_values("评论数", ascending=False)

    # 店铺综合排名（贝叶斯平滑）
    def shop_ranking(self) -> pd.DataFrame:
        df = self.df.dropna(subset=["review_score"])
        global_mean = df["review_score"].mean()
        m = 30  # 先验样本量

        grp = df.groupby(["shop_id", "shop_name"]).agg(
            评论数    = ("review_id", "count"),
            原始均分  = ("review_score", "mean"),
            差评数    = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).sum()),
            总点赞    = ("like_count", "sum"),
        ).reset_index()

        grp["贝叶斯分"] = (
            (global_mean * m + grp["原始均分"] * grp["评论数"]) / (m + grp["评论数"])
        ).round(3)
        grp["差评率%"] = (grp["差评数"] / grp["评论数"] * 100).round(1)

        # 归一化后综合评分
        def _norm(s): return (s - s.min()) / (s.max() - s.min() + 1e-9)
        grp["综合分"] = (
            _norm(grp["贝叶斯分"]) * 0.5
            + _norm(1 - grp["差评率%"] / 100) * 0.3
            + _norm(np.log1p(grp["评论数"])) * 0.2
        ).round(4)
        grp["排名"] = grp["综合分"].rank(ascending=False, method="dense").astype(int)
        grp["评级"] = pd.cut(grp["综合分"],
                              bins=[0, 0.4, 0.6, 0.75, 0.9, 1.01],
                              labels=["D", "C", "B", "A", "S"],
                              include_lowest=True)
        return grp.sort_values("排名")[["排名", "shop_name", "评级", "综合分",
                                        "评论数", "贝叶斯分", "差评率%", "总点赞"]]

    # 数值特征相关矩阵
    def correlation_matrix(self) -> pd.DataFrame:
        cols = [c for c in ["review_score", "like_count", "reply_count", "content_len",
                             "taste_score", "environment_score", "service_score",
                             "sentiment_label"] if c in self.df.columns]
        return self.df[cols].corr().round(3)


# ─────────────────────────────────────────────────────────────
# Part 3-② 序列数据：时间规律 + 用户流失 RFM
# ─────────────────────────────────────────────────────────────

class SequentialAnalyzer:
    """序列数据分析：时段规律、差评爆发检测、RFM 用户分层"""

    def __init__(self, df: pd.DataFrame):
        df = df.copy()
        df["review_time"] = pd.to_datetime(df.get("review_time"), errors="coerce")
        self.df = df.dropna(subset=["review_time"])
        self.df["_hour"]    = self.df["review_time"].dt.hour
        self.df["_weekday"] = self.df["review_time"].dt.dayofweek
        self.df["_date"]    = self.df["review_time"].dt.date
        self.ref = self.df["review_time"].max()

    WEEKDAY = {0:"周一",1:"周二",2:"周三",3:"周四",4:"周五",5:"周六",6:"周日"}

    # 各小时评论量
    def hourly_stats(self) -> pd.DataFrame:
        grp = self.df.groupby("_hour").agg(
            评论数 = ("review_id", "count"),
            平均分 = ("review_score", "mean"),
            差评率 = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean() * 100),
        ).reset_index().rename(columns={"_hour": "小时", "差评率": "差评率%"})
        grp["建议"] = grp["评论数"].apply(
            lambda c: "高峰：增派人手" if c >= grp["评论数"].quantile(0.75)
            else ("低谷：可减少人员" if c <= grp["评论数"].quantile(0.25) else "正常运营")
        )
        return grp.round(2)

    # 星期评论量
    def weekday_stats(self) -> pd.DataFrame:
        grp = self.df.groupby("_weekday").agg(
            评论数 = ("review_id", "count"),
            平均分 = ("review_score", "mean"),
            差评率 = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean() * 100),
        ).reset_index().rename(columns={"差评率": "差评率%"})
        grp["星期"] = grp["_weekday"].map(self.WEEKDAY)
        return grp.drop(columns="_weekday").round(2)

    # 月度趋势
    def monthly_trend(self) -> pd.DataFrame:
        self.df["_month"] = self.df["review_time"].dt.to_period("M").astype(str)
        return self.df.groupby("_month").agg(
            评论数 = ("review_id", "count"),
            平均分 = ("review_score", "mean"),
            差评率 = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean() * 100),
        ).reset_index().rename(columns={"_month": "月份", "差评率": "差评率%"}).round(2)

    # 差评爆发检测（Z-Score）
    def detect_burst(self, window: int = 3, threshold: float = 2.0) -> pd.DataFrame:
        self.df["_is_neg"] = pd.to_numeric(self.df.get("sentiment_label", 0), errors="coerce") == -1
        daily = self.df.groupby("_date").agg(
            总数  = ("review_id", "count"),
            差评数 = ("_is_neg", "sum"),
        ).reset_index()
        daily["差评率"] = daily["差评数"] / daily["总数"]
        rm = daily["差评率"].rolling(window, min_periods=1)
        daily["Z分"] = ((daily["差评率"] - rm.mean()) / (rm.std().fillna(0.01))).round(2)
        daily["风险"] = pd.cut(daily["Z分"], bins=[-np.inf,1,2,3,np.inf],
                                labels=["正常","关注","预警","危机"])
        return daily.sort_values("_date")

    # RFM 用户分层
    def rfm_segments(self) -> pd.DataFrame:
        df = self.df.copy()
        df["review_score"]    = pd.to_numeric(df.get("review_score", 3), errors="coerce")
        df["sentiment_label"] = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce")

        grp = df.groupby("user_id").agg(
            上次评论   = ("review_time", "max"),
            评论次数   = ("review_id", "count"),
            平均分     = ("review_score", "mean"),
            差评次数   = ("sentiment_label", lambda x: (x == -1).sum()),
            用户名     = ("username", "first"),
        ).reset_index()

        grp["距今天数"] = (self.ref - grp["上次评论"]).dt.days
        grp["差评率"]  = (grp["差评次数"] / grp["评论次数"]).round(3)

        def _seg(r):
            d, f = r["距今天数"], r["评论次数"]
            if d <= 14 and f >= 3:  return "高价值活跃"
            if d <= 14:             return "普通活跃"
            if d <= 60 and r["差评率"] > 0.5: return "流失风险"
            if d <= 60:             return "沉睡用户"
            return "已流失"

        grp["用户类型"] = grp.apply(_seg, axis=1)
        action = {"高价值活跃":"发放专属会员权益","普通活跃":"推送新菜/满减",
                  "沉睡用户":"7天时限折扣券","流失风险":"电话回访+大额补偿","已流失":"季度福利推送"}
        grp["运营建议"] = grp["用户类型"].map(action)
        return grp.drop(columns="上次评论").round({"平均分":2,"差评率":3})


# ─────────────────────────────────────────────────────────────
# Part 3-③ 图数据：菜品共现 + KOL识别 + 店铺相似度
# ─────────────────────────────────────────────────────────────

class GraphAnalyzer:
    """图数据分析：菜品关联、用户影响力、店铺相似度"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df["dish_list"] = self.df.get("dishes", pd.Series()).fillna("").apply(
            lambda x: [d.strip() for d in str(x).split("|") if d.strip()]
        )

    # 菜品情感得分
    def dish_sentiment(self) -> pd.DataFrame:
        records = []
        for _, row in self.df.iterrows():
            s = pd.to_numeric(row.get("sentiment_label", 0), errors="coerce") or 0
            sc = pd.to_numeric(row.get("review_score", 3), errors="coerce") or 3
            for d in row.get("dish_list", []):
                records.append({"菜品": d, "情感": s, "评分": sc})
        if not records:
            return pd.DataFrame()
        ddf = pd.DataFrame(records)
        res = ddf.groupby("菜品").agg(
            提及次数 = ("菜品", "count"),
            平均分   = ("评分", "mean"),
            正评率   = ("情感", lambda x: (x == 1).mean() * 100),
            负评率   = ("情感", lambda x: (x == -1).mean() * 100),
        ).reset_index().rename(columns={"正评率": "正评率%", "负评率": "负评率%"})
        res["建议"] = res.apply(
            lambda r: "爆款保留" if r["正评率%"] >= 60 and r["提及次数"] >= 3
            else ("考虑改良" if r["负评率%"] >= 40 else "持续观察"), axis=1
        )
        return res.sort_values("提及次数", ascending=False).round({"平均分":2,"正评率%":1,"负评率%":1})

    # 菜品共现（推荐搭配）
    def dish_cooccurrence(self, top_n: int = 20) -> pd.DataFrame:
        cnt = Counter()
        for dl in self.df["dish_list"]:
            if len(dl) >= 2:
                for pair in combinations(sorted(set(dl)), 2):
                    cnt[pair] += 1
        return pd.DataFrame(
            [{"菜品A": a, "菜品B": b, "共现次数": c} for (a, b), c in cnt.most_common(top_n)]
        )

    # 高影响力用户（KOL）
    def influencer_users(self, top_n: int = 15) -> pd.DataFrame:
        if "user_id" not in self.df.columns:
            return pd.DataFrame()
        grp = self.df.groupby("user_id").agg(
            用户名   = ("username", "first"),
            评论数   = ("review_id", "count"),
            总点赞   = ("like_count", "sum"),
            平均分   = ("review_score", "mean"),
            等级     = ("user_level", "first"),
        ).reset_index()
        grp["等级"] = pd.to_numeric(grp["等级"], errors="coerce").fillna(1)
        grp["影响力"] = (
            np.log1p(grp["评论数"]) * 0.4
            + np.log1p(grp["总点赞"]) * 0.4
            + grp["等级"] / 10 * 0.2
        ).round(3)
        grp["层级"] = pd.cut(grp["影响力"], bins=[-np.inf,0.5,1.0,1.5,np.inf],
                              labels=["普通","活跃","超级用户","KOL"])
        return grp.nlargest(top_n, "影响力")[["用户名","层级","评论数","总点赞","影响力"]].round({"平均分":2})


# ─────────────────────────────────────────────────────────────
# Part 4-① 时空数据：城市分析 + 时段热力 + 选址评估
# ─────────────────────────────────────────────────────────────

class SpatiotemporalAnalyzer:
    """时空数据分析：城市维度、时段热力矩阵、选址建议"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df["review_time"] = pd.to_datetime(self.df.get("review_time"), errors="coerce")
        # 从 shop_name 推断城市（无 city 字段时）
        if "city" not in self.df.columns:
            cities = ["北京","上海","成都","广州","深圳","杭州","南京","武汉","重庆","西安"]
            def _city(name):
                for c in cities:
                    if c in str(name): return c
                return "其他"
            self.df["city"] = self.df.get("shop_name", pd.Series()).apply(_city)

    # 城市汇总
    def city_summary(self) -> pd.DataFrame:
        grp = self.df.groupby("city").agg(
            评论数 = ("review_id", "count"),
            店铺数 = ("shop_id", "nunique"),
            平均分 = ("review_score", "mean"),
            差评率 = ("sentiment_label", lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean() * 100),
        ).reset_index().rename(columns={"差评率": "差评率%"})
        grp["人均评论"] = (grp["评论数"] / grp["店铺数"]).round(1)
        grp["市场热度"] = pd.cut(grp["评论数"], bins=[0,50,200,500,np.inf],
                                  labels=["冷门","成长","活跃","热门"])
        return grp.sort_values("评论数", ascending=False).round({"平均分":2,"差评率%":1})

    # 城市 × 时段热力矩阵
    def spatiotemporal_heatmap(self) -> pd.DataFrame:
        valid = self.df.dropna(subset=["review_time"])
        valid["时段"] = pd.cut(
            valid["review_time"].dt.hour,
            bins=[0,6,10,14,17,21,24],
            labels=["凌晨","早餐","午餐","下午","晚餐","宵夜"],
            include_lowest=True,
        )
        return valid.groupby(["city","时段"]).size().unstack(fill_value=0)

    # 选址综合评分
    def site_score(self) -> pd.DataFrame:
        cs = self.city_summary()
        if cs.empty: return cs
        def _n(s): return (s - s.min()) / (s.max() - s.min() + 1e-9)
        cs["选址分"] = (
            _n(cs["平均分"]) * 0.4
            + _n(cs["评论数"]) * 0.3
            + _n(1 - cs["差评率%"] / 100) * 0.3
        ).round(3)
        cs["评级"] = pd.cut(cs["选址分"], bins=[-np.inf,0.3,0.5,0.7,np.inf],
                             labels=["D观望","C谨慎","B推荐","A优选"])
        return cs[["city","评级","选址分","评论数","店铺数","平均分","差评率%"]].sort_values("选址分",ascending=False)

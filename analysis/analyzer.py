# -*- coding: utf-8 -*-
"""
核心分析模块 — 无状态接口，所有方法直接接收 df 参数
保留：表格数据 / 序列数据
精简：已移除图数据（GraphAnalyzer）与时空数据（SpatiotemporalAnalyzer）
深化：TabularAnalyzer 新增 Wilson Score 排名 + KMeans 餐厅聚类
      SequentialAnalyzer 新增 STL 趋势分解 + 线性预测 + KMeans RFM 聚类
"""

import warnings
from typing import Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────
# 内部工具
# ─────────────────────────────────────────────────────────────
def _num(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _norm(s: pd.Series) -> pd.Series:
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn + 1e-9)


# ═════════════════════════════════════════════════════════════
# Part 3-①  表格数据
# ═════════════════════════════════════════════════════════════
class TabularAnalyzer:

    # ── 基础统计 ──────────────────────────────────────────────
    def eda_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        score = _num(df, "review_score")
        rows = [
            ("总评论数",   len(df)),
            ("店铺数",     df["shop_id"].nunique() if "shop_id" in df.columns else 0),
            ("用户数",     df["user_id"].nunique() if "user_id" in df.columns else 0),
            ("城市数",     df["city"].nunique() if "city" in df.columns else 0),
            ("平均评分",   round(score.mean(), 3)),
            ("评分标准差", round(score.std(), 3)),
            ("正面评论数", int((df["sentiment"] == "positive").sum())
             if "sentiment" in df.columns else 0),
            ("负面评论数", int((df["sentiment"] == "negative").sum())
             if "sentiment" in df.columns else 0),
            ("均评论长度", round(_num(df, "content_len").mean(), 1)),
        ]
        return pd.DataFrame(rows, columns=["指标", "值"])

    # ── 贝叶斯排名（基线） ────────────────────────────────────
    def bayesian_ranking(self, df: pd.DataFrame, min_reviews: int = 5) -> pd.DataFrame:
        """先验 m=30 贝叶斯平滑排名"""
        score = _num(df, "review_score")
        global_mean = score.mean()
        m = 30

        extra = {c: (c, "first") for c in ["city", "district", "category"]
                 if c in df.columns}
        agg = {"review_count": ("review_id", "count"),
               "avg_score":    ("review_score", "mean")}
        agg.update(extra)

        if "sentiment_label" in df.columns:
            agg["neg_count"] = (
                "sentiment_label",
                lambda x: (pd.to_numeric(x, errors="coerce") == -1).sum()
            )

        grp = df.groupby(["shop_id", "shop_name"]).agg(**agg).reset_index()
        grp = grp[grp["review_count"] >= min_reviews].copy()

        avg = pd.to_numeric(grp["avg_score"], errors="coerce")
        cnt = grp["review_count"]
        grp["bayes_score"] = ((global_mean * m + avg * cnt) / (m + cnt)).round(3)
        grp["neg_rate"] = (
            (grp["neg_count"] / cnt * 100).round(1)
            if "neg_count" in grp.columns else 0.0
        )
        grp["bayes_rank"] = grp["bayes_score"].rank(
            ascending=False, method="dense").astype(int)
        return grp.sort_values("bayes_rank")

    # ── Wilson Score 排名（深化） ─────────────────────────────
    def wilson_ranking(self, df: pd.DataFrame, min_reviews: int = 5) -> pd.DataFrame:
        """
        Wilson Score 置信下界排名（95% 置信水平）。
        将均分归一化为二项比例 p = (avg_score-1)/4，
        计算下界后映射回 [1,5]。
        低评论量店铺因区间更宽受到更重惩罚，
        统计严格性优于贝叶斯平滑。
        同时保留贝叶斯排名用于对比排名漂移量。
        """
        Z = 1.96

        extra = {c: (c, "first") for c in ["city", "category"] if c in df.columns}
        agg = {"review_count": ("review_id", "count"),
               "avg_score":    ("review_score", "mean")}
        agg.update(extra)

        grp = df.groupby(["shop_id", "shop_name"]).agg(**agg).reset_index()
        grp = grp[grp["review_count"] >= min_reviews].copy()

        n = grp["review_count"].astype(float)
        p = ((pd.to_numeric(grp["avg_score"], errors="coerce") - 1) / 4.0).clip(0, 1)

        denom  = 1 + Z ** 2 / n
        centre = p + Z ** 2 / (2 * n)
        spread = Z * np.sqrt(p * (1 - p) / n + Z ** 2 / (4 * n ** 2))
        lower  = ((centre - spread) / denom).clip(0, 1)

        grp["wilson_lower"] = lower.round(4)
        grp["wilson_score"] = (lower * 4 + 1).round(3)
        grp["wilson_rank"]  = grp["wilson_score"].rank(
            ascending=False, method="dense").astype(int)

        # 合并贝叶斯排名，计算位次漂移
        bayes = self.bayesian_ranking(df, min_reviews)[
            ["shop_id", "bayes_score", "bayes_rank", "neg_rate"]
        ]
        grp = grp.merge(bayes, on="shop_id", how="left")
        grp["rank_drift"] = (grp["bayes_rank"] - grp["wilson_rank"]).fillna(0).astype(int)
        return grp.sort_values("wilson_rank")

    # ── KMeans 餐厅聚类（深化） ──────────────────────────────
    def restaurant_clustering(
        self, df: pd.DataFrame, n_clusters: int = 4
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        KMeans 聚类餐厅（均分 / 评论量 / 差评率 / 平均评论长度）。
        按质心均分降序为聚类命名：Premium > Good > Average > At Risk。
        返回 (明细 DataFrame, 各聚类汇总 DataFrame)。
        """
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        agg: dict = {
            "review_count": ("review_id",    "count"),
            "avg_score":    ("review_score", "mean"),
        }
        if "content_len" in df.columns:
            agg["avg_len"] = ("content_len", "mean")

        grp = df.groupby(["shop_id", "shop_name"]).agg(**agg).reset_index()

        if "sentiment_label" in df.columns:
            neg = (
                df.groupby("shop_id")["sentiment_label"]
                .apply(lambda x: (pd.to_numeric(x, errors="coerce") == -1).mean())
                .reset_index()
                .rename(columns={"sentiment_label": "neg_rate"})
            )
            grp = grp.merge(neg, on="shop_id", how="left")
        else:
            grp["neg_rate"] = 0.0

        feats = [c for c in ["avg_score", "review_count", "neg_rate", "avg_len"]
                 if c in grp.columns]
        X = grp[feats].fillna(0).values

        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)
        km     = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        grp["cluster"] = km.fit_predict(X_sc)

        centroids = pd.DataFrame(scaler.inverse_transform(km.cluster_centers_),
                                 columns=feats)
        tier_labels = ["Premium", "Good", "Average", "At Risk",
                       "Tier-5", "Tier-6", "Tier-7", "Tier-8"][:n_clusters]
        order = centroids["avg_score"].sort_values(ascending=False).index.tolist()
        label_map = {c: tier_labels[i] for i, c in enumerate(order)}
        grp["cluster_label"] = grp["cluster"].map(label_map)

        summary = (
            grp.groupby("cluster_label")
            .agg(shop_count=("shop_id", "count"),
                 mean_score=("avg_score", "mean"),
                 mean_reviews=("review_count", "mean"),
                 mean_neg_rate=("neg_rate", "mean"))
            .round({"mean_score": 3, "mean_reviews": 1, "mean_neg_rate": 3})
            .reset_index()
            .sort_values("mean_score", ascending=False)
        )
        detail = grp.sort_values(["cluster_label", "avg_score"],
                                 ascending=[True, False])
        return detail, summary

    # ── 相关性分析 ────────────────────────────────────────────
    def correlation_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in ["review_score", "like_count", "reply_count",
                             "content_len", "sentiment_label", "aspect_count"]
                if c in df.columns]
        return df[cols].apply(pd.to_numeric, errors="coerce").corr().round(3)


# ═════════════════════════════════════════════════════════════
# Part 3-②  序列数据
# ═════════════════════════════════════════════════════════════
class SequentialAnalyzer:

    def _prep(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["review_time"] = pd.to_datetime(df.get("review_time"), errors="coerce")
        return df.dropna(subset=["review_time"])

    # ── 基础时段 ──────────────────────────────────────────────
    def hourly_pattern(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._prep(df)
        df["review_hour"] = df["review_time"].dt.hour
        return (df.groupby("review_hour")
                  .agg(count=("review_id", "count"))
                  .reset_index()
                  .sort_values("review_hour"))

    def monthly_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._prep(df)
        df["year_month"] = df["review_time"].dt.to_period("M").astype(str)
        return (df.groupby("year_month")
                  .agg(count=("review_id", "count"),
                       avg_score=("review_score", "mean"))
                  .reset_index()
                  .sort_values("year_month"))

    # ── 差评爆发检测 ──────────────────────────────────────────
    def burst_detection(self, df: pd.DataFrame,
                        window: int = 7, threshold: float = 2.0) -> pd.DataFrame:
        """滚动 Z-Score 差评爆发检测"""
        df = self._prep(df)
        df["_date"] = df["review_time"].dt.date
        df["_neg"]  = (pd.to_numeric(
            df.get("sentiment_label", 0), errors="coerce") == -1)
        daily = df.groupby("_date").agg(
            total=("review_id", "count"), neg=("_neg", "sum")
        ).reset_index()
        daily["neg_rate"] = daily["neg"] / daily["total"]
        rm = daily["neg_rate"].rolling(window, min_periods=1)
        daily["z_score"] = (
            (daily["neg_rate"] - rm.mean()) / rm.std().fillna(0.01)
        ).round(2)
        daily["alert"] = daily["z_score"] >= threshold
        return daily.sort_values("_date")

    # ── STL 趋势分解（深化） ──────────────────────────────────
    def trend_decomposition(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        月度时序分解：趋势 / 季节 / 残差三分量。
        优先调用 statsmodels STL（周期=12，robust=True），
        降级回退至 12 期中心移动平均（Classical Additive）。
        返回含 trend / seasonal / residual / method 列的 DataFrame。
        """
        ts = self.monthly_trend(df).copy()
        if ts.empty:
            return ts

        # 尝试 STL
        if len(ts) >= 24:
            try:
                from statsmodels.tsa.seasonal import STL
                idx = pd.PeriodIndex(ts["year_month"], freq="M")
                ser = pd.Series(ts["count"].values, index=idx, dtype=float)
                res = STL(ser, period=12, robust=True).fit()
                ts["trend"]    = res.trend.values
                ts["seasonal"] = res.seasonal.values
                ts["residual"] = res.resid.values
                ts["method"]   = "STL"
                return ts
            except Exception:
                pass

        # 回退：12 期 CMA
        ts["trend"]    = ts["count"].rolling(12, center=True, min_periods=6).mean()
        trend_filled   = ts["trend"].fillna(ts["count"].mean())
        ts["seasonal"] = ts["count"] - trend_filled
        ts["residual"] = 0.0
        ts["method"]   = "CMA-12"
        return ts

    # ── 线性趋势预测（深化） ──────────────────────────────────
    def forecast_trend(self, df: pd.DataFrame, steps: int = 6) -> pd.DataFrame:
        """
        在 STL/CMA 趋势分量上拟合线性回归并外推未来 steps 个月。
        返回 type='actual'|'forecast' 列的 DataFrame，
        forecast 行的 count 为预测评论量（剔除负数）。
        """
        from sklearn.linear_model import LinearRegression

        decomp = self.trend_decomposition(df).dropna(subset=["trend"]).copy()
        if len(decomp) < 6:
            return decomp

        t = np.arange(len(decomp)).reshape(-1, 1)
        lr = LinearRegression().fit(t, decomp["trend"].values)

        t_fc   = np.arange(len(decomp), len(decomp) + steps).reshape(-1, 1)
        y_pred = lr.predict(t_fc)

        last = pd.Period(decomp["year_month"].iloc[-1], freq="M")
        fc_months = [(last + i + 1).strftime("%Y-%m") for i in range(steps)]

        forecast = pd.DataFrame({
            "year_month": fc_months,
            "count":      np.maximum(y_pred, 0).round().astype(int),
            "avg_score":  np.nan,
            "trend":      y_pred,
            "seasonal":   0.0,
            "residual":   0.0,
            "method":     decomp["method"].iloc[-1],
            "type":       "forecast",
        })
        decomp["type"] = "actual"
        return pd.concat([decomp, forecast], ignore_index=True)

    # ── 规则 RFM（基线） ─────────────────────────────────────
    def rfm_segmentation(self, df: pd.DataFrame) -> pd.DataFrame:
        """四分位规则 RFM 分层（保留作基线对比）"""
        df = self._prep(df)
        ref = df["review_time"].max()
        grp = df.groupby("user_id").agg(
            last_review=("review_time", "max"),
            F=("review_id",    "count"),
            M=("review_score", "mean"),
        ).reset_index()
        grp["R"] = (ref - grp["last_review"]).dt.days

        for col, asc in [("R", True), ("F", False), ("M", False)]:
            try:
                grp[f"{col}_score"] = pd.qcut(
                    grp[col], q=4,
                    labels=[4, 3, 2, 1] if asc else [1, 2, 3, 4],
                    duplicates="drop"
                ).astype(float)
            except Exception:
                grp[f"{col}_score"] = 2.0

        grp["rfm_total"] = grp["R_score"] + grp["F_score"] + grp["M_score"]

        def _seg(row):
            r, f = row["R_score"], row["F_score"]
            if r >= 3 and f >= 3:     return "Champions"
            if r >= 3:                return "Recent Users"
            if f >= 3:                return "Loyal Users"
            if row["rfm_total"] >= 8: return "Potential"
            return "At Risk"

        grp["segment"] = grp.apply(_seg, axis=1)
        return grp[["user_id", "R", "F", "M",
                    "R_score", "F_score", "M_score",
                    "rfm_total", "segment"]].round({"R": 0, "F": 0, "M": 2})

    # ── KMeans RFM 聚类（深化） ──────────────────────────────
    def rfm_clustering(
        self, df: pd.DataFrame, n_clusters: int = 5
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        KMeans 数据驱动 RFM 用户聚类。
        特征：[-R, F, M]（R 取反使大值=近期）经 StandardScaler 标准化。
        质心综合分 = neg_R + F + M，降序命名：
        Champions / Loyal / Potential / At Risk / Inactive。
        返回 (明细 DataFrame, 各聚类汇总 DataFrame)。
        """
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        rfm = self.rfm_segmentation(df)
        X   = rfm[["R", "F", "M"]].copy()
        X["R"] = -X["R"]          # 取反：近期 → 大值

        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)
        km     = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        rfm["km_cluster"] = km.fit_predict(X_sc)

        c_raw = pd.DataFrame(
            scaler.inverse_transform(km.cluster_centers_),
            columns=["neg_R", "F", "M"]
        )
        c_raw["composite"] = c_raw["neg_R"] + c_raw["F"] + c_raw["M"]
        ordered = c_raw.sort_values("composite", ascending=False).index.tolist()
        seg_names = ["Champions", "Loyal", "Potential", "At Risk", "Inactive",
                     "Tier-6", "Tier-7", "Tier-8"][:n_clusters]
        label_map = {c: seg_names[i] for i, c in enumerate(ordered)}
        rfm["km_segment"] = rfm["km_cluster"].map(label_map)

        summary = (
            rfm.groupby("km_segment")
            .agg(user_count=("user_id", "count"),
                 avg_R=("R", "mean"),
                 avg_F=("F", "mean"),
                 avg_M=("M", "mean"))
            .round(1)
            .reset_index()
            .sort_values("avg_F", ascending=False)
        )
        return rfm, summary

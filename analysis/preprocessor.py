# -*- coding: utf-8 -*-
"""
表格数据预处理模块 — Part 3: 表格数据
对加载后的 DataFrame 进行清洗、类型转换、标准化
输出：干净、结构化、可直接用于分析和建模的 DataFrame
"""

import re
import json
import pandas as pd
import numpy as np
from typing import Optional


class ReviewPreprocessor:
    """
    评论表格数据预处理器
    处理步骤:
      1. 基础类型转换（评分、时间、布尔值）
      2. 文本字段清洗（去除噪声）
      3. 结构化字段解析（score_text → 口味/环境/服务三列）
      4. 衍生特征计算（文本长度、时间特征）
      5. 缺失值处理策略
      6. 异常值过滤
    """

    # 情感标签映射
    SENTIMENT_MAP = {"positive": 1, "neutral": 0, "negative": -1}

    def __init__(self, min_content_len: int = 5, max_content_len: int = 2000):
        self.min_content_len = min_content_len
        self.max_content_len = max_content_len

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """完整预处理流程（入口方法）"""
        print(f"[预处理] 输入: {len(df)} 行")
        df = df.copy()
        df = self._cast_types(df)
        df = self._parse_score_text(df)
        df = self._clean_text(df)
        df = self._add_derived_features(df)
        df = self._handle_missing(df)
        df = self._filter_outliers(df)
        print(f"[预处理] 输出: {len(df)} 行 (过滤 {len(df)} 条后)")
        return df.reset_index(drop=True)

    # ── Step 1: 类型转换 ─────────────────────────────────────

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """字段类型标准化"""
        # 数值型
        for col in ["review_score", "like_count", "reply_count", "user_level"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 评分裁剪到合法区间 [1, 5]
        if "review_score" in df.columns:
            df["review_score"] = df["review_score"].clip(1, 5)

        # 布尔型
        if "vip_status" in df.columns:
            df["vip_status"] = df["vip_status"].map(
                {"True": True, "False": False, True: True, False: False, 1: True, 0: False}
            ).fillna(False).astype(bool)

        # 时间型
        if "review_time" in df.columns:
            df["review_time"] = pd.to_datetime(df["review_time"], errors="coerce")
        if "crawl_time" in df.columns:
            df["crawl_time"] = pd.to_datetime(df["crawl_time"], errors="coerce")

        # 情感标签统一
        if "sentiment_label" in df.columns:
            df["sentiment_label"] = pd.to_numeric(df["sentiment_label"], errors="coerce")
        if "sentiment" in df.columns and "sentiment_label" not in df.columns:
            df["sentiment_label"] = df["sentiment"].map(self.SENTIMENT_MAP)

        return df

    # ── Step 2: 解析 score_text ──────────────────────────────

    def _parse_score_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将 "口味5.0 | 环境4.8 | 服务5.0" 解析为独立三列
        taste_score / environment_score / service_score
        """
        if "score_text" not in df.columns:
            return df

        def _extract(text: str, keyword: str) -> Optional[float]:
            if not isinstance(text, str):
                return None
            m = re.search(rf"{keyword}(\d+(?:\.\d+)?)", text)
            return float(m.group(1)) if m else None

        df["taste_score"]       = df["score_text"].apply(lambda x: _extract(x, "口味"))
        df["environment_score"] = df["score_text"].apply(lambda x: _extract(x, "环境"))
        df["service_score"]     = df["score_text"].apply(lambda x: _extract(x, "服务"))

        return df

    # ── Step 3: 文本清洗 ─────────────────────────────────────

    def _clean_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """对评论正文做轻量清洗（不破坏语义）"""
        if "review_content" not in df.columns:
            return df

        df["review_content"] = (
            df["review_content"]
            .fillna("")
            .str.strip()
            # 折叠连续空白
            .str.replace(r"\s+", " ", regex=True)
            # 去除零宽字符
            .str.replace(r"[\u200b-\u200f\ufeff]", "", regex=True)
        )
        return df

    # ── Step 4: 衍生特征 ─────────────────────────────────────

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """从现有列计算衍生特征"""

        # 文本长度
        if "review_content" in df.columns:
            df["content_len"] = df["review_content"].str.len()

        # 是否带图片
        if "images" in df.columns:
            df["has_image"] = df["images"].fillna("").str.strip().ne("")

        # 时间衍生特征
        if "review_time" in df.columns and pd.api.types.is_datetime64_any_dtype(df["review_time"]):
            df["review_year"]    = df["review_time"].dt.year
            df["review_month"]   = df["review_time"].dt.month
            df["review_weekday"] = df["review_time"].dt.dayofweek   # 0=周一
            df["review_hour"]    = df["review_time"].dt.hour
            df["is_weekend"]     = df["review_weekday"].isin([5, 6])

        # 菜品数量
        if "dishes" in df.columns:
            df["dish_count"] = (
                df["dishes"].fillna("").apply(
                    lambda x: len([d for d in str(x).split("|") if d.strip()])
                )
            )

        # 是否高质量评论（长度>20 + 有图 + 有评分文本）
        quality_mask = pd.Series(True, index=df.index)
        if "content_len" in df.columns:
            quality_mask &= df["content_len"] >= 20
        if "score_text" in df.columns:
            quality_mask &= df["score_text"].fillna("").ne("")
        df["is_quality_review"] = quality_mask

        # ABSA 方面数量
        if "absa_aspects" in df.columns:
            def _count_aspects(x):
                if pd.isna(x) or not x:
                    return 0
                try:
                    parsed = json.loads(x) if isinstance(x, str) else x
                    return len(parsed) if isinstance(parsed, list) else 0
                except Exception:
                    return 0
            df["aspect_count"] = df["absa_aspects"].apply(_count_aspects)

        return df

    # ── Step 5: 缺失值处理 ───────────────────────────────────

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """策略：数值填0，文本填空串，分类填 unknown"""
        fill_zero   = ["like_count", "reply_count", "user_level", "aspect_count", "dish_count"]
        fill_str    = ["username", "order_type", "dishes", "images", "score_text", "business_reply"]
        fill_mean   = ["taste_score", "environment_score", "service_score"]

        for col in fill_zero:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        for col in fill_str:
            if col in df.columns:
                df[col] = df[col].fillna("")

        for col in fill_mean:
            if col in df.columns:
                mean_val = df[col].mean()
                df[col] = df[col].fillna(round(mean_val, 1) if not pd.isna(mean_val) else 0)

        if "sentiment_label" in df.columns:
            df["sentiment_label"] = df["sentiment_label"].fillna(0).astype(int)

        return df

    # ── Step 6: 异常值过滤 ───────────────────────────────────

    def _filter_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤不合法数据行"""
        original_len = len(df)

        # 过滤空评论
        if "review_content" in df.columns:
            df = df[df["review_content"].str.len() >= self.min_content_len]

        # 截断过长评论
        if "review_content" in df.columns:
            df["review_content"] = df["review_content"].str[:self.max_content_len]

        # 过滤评分超范围
        if "review_score" in df.columns:
            df = df[df["review_score"].between(1, 5)]

        filtered = original_len - len(df)
        if filtered > 0:
            print(f"  [过滤] 移除异常/空评论 {filtered} 条")
        return df


def preprocess(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """快捷函数：一行完成预处理"""
    return ReviewPreprocessor(**kwargs).fit_transform(df)

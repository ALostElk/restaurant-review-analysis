# -*- coding: utf-8 -*-
"""
数据加载模块 — Part 2: 数据处理流程
支持从 CSV / JSON / MongoDB / MySQL 四种来源统一加载评论数据
最终输出标准化的 pandas DataFrame，供下游分析使用
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import Optional, Union
from datetime import datetime


# ── 标准列定义（所有数据源对齐到同一 schema）───────────────────
STANDARD_COLUMNS = [
    "review_id",        # 评论唯一ID
    "shop_id",          # 店铺ID
    "shop_name",        # 店铺名称
    "platform",         # 来源平台: dianping / meituan
    "user_id",          # 用户ID
    "username",         # 用户昵称
    "user_level",       # 用户等级
    "vip_status",       # VIP状态
    "review_content",   # 评论正文
    "review_score",     # 综合评分 (1-5)
    "score_text",       # 口味/环境/服务文本评分
    "review_time",      # 评论时间
    "like_count",       # 点赞数
    "reply_count",      # 回复数
    "order_type",       # 消费类型: 堂食/外卖/打包
    "dishes",           # 菜品（"|"分隔）
    "images",           # 图片URL（"|"分隔）
    "sentiment_label",  # 情感标签: 1正/0中/-1负
    "sentiment",        # 情感文字: positive/neutral/negative
    "absa_aspects",     # ABSA标注 JSON字符串
    "crawl_time",       # 采集时间
]


class ReviewDataLoader:
    """
    餐饮评论数据加载器
    统一接口：无论数据来自哪种存储，都返回相同结构的 DataFrame
    """

    # ── 从 CSV 加载 ──────────────────────────────────────────

    @staticmethod
    def from_csv(path: Union[str, Path], encoding: str = "utf-8-sig") -> pd.DataFrame:
        """
        加载 CSV 文件
        :param path: CSV 文件路径
        :param encoding: 文件编码（utf-8-sig 兼容 Excel 导出的 BOM）
        """
        df = pd.read_csv(path, encoding=encoding, low_memory=False)
        print(f"[CSV] 加载完成: {path}")
        print(f"      行数={len(df)}, 列数={len(df.columns)}")
        return ReviewDataLoader._align_columns(df)

    # ── 从 JSON 加载 ─────────────────────────────────────────

    @staticmethod
    def from_json(path: Union[str, Path]) -> pd.DataFrame:
        """
        加载 JSON 文件
        支持两种格式:
          1. 列表格式: [{...}, {...}]
          2. 包含 reviews 键的字典: {"reviews": [...], "meta": {...}}
        """
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            records = raw.get("reviews", raw.get("data", [raw]))
        else:
            raise ValueError(f"不支持的 JSON 结构: {type(raw)}")

        df = pd.json_normalize(records)
        print(f"[JSON] 加载完成: {path}")
        print(f"       记录数={len(df)}")
        return ReviewDataLoader._align_columns(df)

    # ── 从 MongoDB 加载 ──────────────────────────────────────

    @staticmethod
    def from_mongodb(
        host: str = "localhost",
        port: int = 27017,
        db_name: str = "restaurant_reviews",
        collection: str = "reviews",
        user: str = "",
        password: str = "",
        query: dict = None,
        limit: int = 0,
    ) -> pd.DataFrame:
        """
        从 MongoDB 加载评论数据
        :param query:  MongoDB 查询条件，如 {"platform": "dianping"}
        :param limit:  限制条数（0=不限制）
        """
        try:
            import pymongo
        except ImportError:
            raise ImportError("请安装 pymongo: pip install pymongo")

        if user and password:
            uri = f"mongodb://{user}:{password}@{host}:{port}/{db_name}?authSource=admin"
        else:
            uri = f"mongodb://{host}:{port}/"

        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
        col = client[db_name][collection]
        cursor = col.find(query or {}, {"_id": 0})
        if limit > 0:
            cursor = cursor.limit(limit)

        records = list(cursor)
        client.close()

        df = pd.json_normalize(records)
        print(f"[MongoDB] 加载完成: {db_name}.{collection}")
        print(f"          记录数={len(df)}")
        return ReviewDataLoader._align_columns(df)

    # ── 从 MySQL 加载 ────────────────────────────────────────

    @staticmethod
    def from_mysql(
        host: str = "localhost",
        port: int = 3306,
        db_name: str = "restaurant_reviews",
        user: str = "crawler",
        password: str = "crawler123",
        sql: str = "SELECT * FROM review WHERE is_spam=0 LIMIT 10000",
    ) -> pd.DataFrame:
        """
        从 MySQL 加载评论数据（使用 SQLAlchemy）
        :param sql: 自定义查询语句，默认加载非垃圾评论
        """
        try:
            from sqlalchemy import create_engine, text
        except ImportError:
            raise ImportError("请安装 sqlalchemy: pip install sqlalchemy")

        dsn = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"
        engine = create_engine(dsn, pool_pre_ping=True)
        df = pd.read_sql(text(sql), engine)
        engine.dispose()

        print(f"[MySQL] 加载完成: {db_name}")
        print(f"        记录数={len(df)}")
        return ReviewDataLoader._align_columns(df)

    # ── 智能加载（根据路径/参数自动判断来源）────────────────────

    @classmethod
    def load(cls, source: str, **kwargs) -> pd.DataFrame:
        """
        智能加载接口
        :param source: 文件路径 (.csv/.json) 或 数据库类型 ("mongodb"/"mysql")
        """
        s = source.lower()
        if s.endswith(".csv"):
            return cls.from_csv(source, **kwargs)
        elif s.endswith(".json"):
            return cls.from_json(source)
        elif s == "mongodb":
            return cls.from_mongodb(**kwargs)
        elif s == "mysql":
            return cls.from_mysql(**kwargs)
        else:
            raise ValueError(f"未识别的数据来源: {source}")

    # ── 内部工具 ─────────────────────────────────────────────

    @staticmethod
    def _align_columns(df: pd.DataFrame) -> pd.DataFrame:
        """对齐列到标准 schema，缺失列补 NaN"""
        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None
        # 只保留标准列（多余的列保留，不截断，方便扩展）
        existing_standard = [c for c in STANDARD_COLUMNS if c in df.columns]
        extra_cols = [c for c in df.columns if c not in STANDARD_COLUMNS]
        return df[existing_standard + extra_cols]

    @staticmethod
    def describe(df: pd.DataFrame) -> None:
        """打印数据集基本信息"""
        print("\n" + "=" * 60)
        print("📋 数据集基本信息")
        print("=" * 60)
        print(f"  总行数:     {len(df):,}")
        print(f"  总列数:     {len(df.columns)}")
        print(f"  内存占用:   {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

        if "platform" in df.columns:
            print(f"\n  平台分布:")
            for p, cnt in df["platform"].value_counts().items():
                print(f"    {p}: {cnt:,} ({cnt/len(df)*100:.1f}%)")

        if "sentiment" in df.columns:
            print(f"\n  情感分布:")
            for s, cnt in df["sentiment"].value_counts().items():
                print(f"    {s}: {cnt:,} ({cnt/len(df)*100:.1f}%)")

        if "review_score" in df.columns:
            scores = pd.to_numeric(df["review_score"], errors="coerce").dropna()
            print(f"\n  评分统计:")
            print(f"    均值={scores.mean():.2f}, 中位数={scores.median():.1f}, "
                  f"标准差={scores.std():.2f}")

        null_cols = df.isnull().sum()
        null_cols = null_cols[null_cols > 0]
        if len(null_cols):
            print(f"\n  缺失值 (Top 5):")
            for col, cnt in null_cols.head(5).items():
                print(f"    {col}: {cnt} ({cnt/len(df)*100:.1f}%)")
        print("=" * 60)

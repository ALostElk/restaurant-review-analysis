# -*- coding: utf-8 -*-
"""
Yelp 数据集加载与转换脚本
数据源: hf://datasets/Johnnyeee/Yelpdata_663/yelptrain_data.parquet

加载方式:
  pandas + hf:// 协议直接引用 HuggingFace 上的 parquet 文件
  用 pyarrow 按行组（row group）读取，只拉取所需行数，不下载完整文件

运行:
  python data/load_yelp.py               # 默认采样 3000 条
  python data/load_yelp.py --sample 5000
  python data/load_yelp.py --local path/to/yelp_train.csv
"""

import os
import csv
import json
import argparse
import hashlib
import sys
from datetime import datetime

import pandas as pd

# 从环境变量读取 HuggingFace Token（不要将 Token 硬编码在代码中）
# 使用前请先执行：export HF_TOKEN="your_token_here"
# 或在 .env 文件中设置 HF_TOKEN=your_token_here
HF_TOKEN = os.environ.get("HF_TOKEN", "")
if not HF_TOKEN:
    raise EnvironmentError(
        "请设置环境变量 HF_TOKEN。\n"
        "  Linux/macOS: export HF_TOKEN='hf_...' \n"
        "  Windows:     $env:HF_TOKEN='hf_...'"
    )
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

HF_TRAIN = "hf://datasets/Johnnyeee/Yelpdata_663/yelptrain_data.parquet"
HF_TEST  = "hf://datasets/Johnnyeee/Yelpdata_663/yelptest_data.parquet"

OUTPUT_DIR  = "data"
REVIEWS_CSV = os.path.join(OUTPUT_DIR, "sample_reviews.csv")
SHOPS_CSV   = os.path.join(OUTPUT_DIR, "sample_shops.csv")


# ── 字段处理工具 ─────────────────────────────────────────────
def _sentiment(stars: float):
    if stars >= 4:  return "positive",  1
    if stars == 3:  return "neutral",   0
    return               "negative", -1

def _category(categories: str) -> str:
    if not categories:
        return "Restaurant"
    priority = ["Pizza","Sushi","Chinese","Mexican","Italian","Burgers","Seafood",
                "Thai","Indian","Japanese","Korean","American","Mediterranean",
                "Sandwiches","Breakfast","Coffee","Bakeries","Fast Food","Bar"]
    for cat in priority:
        if cat in str(categories):
            return cat
    parts = [c.strip() for c in str(categories).split(",")]
    for p in parts:
        if p not in ("Restaurants", "Food", "Nightlife"):
            return p
    return "Restaurant"

ASPECT_KW = {
    "food":     ["food","taste","flavor","delicious","bland","fresh","stale","portion","dish"],
    "service":  ["service","staff","waiter","waitress","server","rude","friendly","slow"],
    "ambiance": ["ambiance","atmosphere","decor","noise","clean","dirty","cozy","crowded"],
    "price":    ["price","expensive","cheap","value","overpriced","affordable","worth","bill"],
    "location": ["location","parking","convenient","far","close","accessible"],
}

def _absa(text: str, sentiment: str) -> str:
    t = text.lower()
    return json.dumps(
        [{"aspect": asp, "sentiment": sentiment}
         for asp, kws in ASPECT_KW.items() if any(k in t for k in kws)],
        ensure_ascii=False
    )


# ══════════════════════════════════════════════════════════════
#  核心加载：pandas hf:// 直接引用 parquet（按行组读取）
# ══════════════════════════════════════════════════════════════
def _load_via_hf_parquet(sample: int) -> pd.DataFrame:
    """
    用 pyarrow 读取 hf:// parquet 第一行组，再从中随机采样。
    行组粒度是 parquet 的最小读取单元，第一行组约 100 万行，
    一次下载即可支持任意 sample 大小（<=100 万）。
    """
    try:
        import pyarrow.parquet as pq
        import fsspec
    except ImportError:
        raise ImportError("请安装: pip install pyarrow fsspec huggingface_hub")

    print(f"正在读取 Yelp parquet（hf:// 协议）...")
    print(f"  路径: {HF_TRAIN}")
    print(f"  目标采样: {sample} 行", flush=True)

    fs      = fsspec.filesystem("hf", token=HF_TOKEN)
    hf_path = HF_TRAIN.replace("hf://", "")

    with fs.open(hf_path, "rb") as f:
        pf = pq.ParquetFile(f)
        print(f"  行组数: {pf.metadata.num_row_groups}  "
              f"每组约 {pf.metadata.row_group(0).num_rows:,} 行", flush=True)
        # 读第一行组（包含约 100 万行，足以支撑 30000 条采样）
        table = pf.read_row_group(0)

    df = table.to_pandas()
    print(f"  行组读取完成: {len(df):,} 行，{len(df.columns)} 列", flush=True)

    if len(df) > sample:
        df = df.sample(n=sample, random_state=42).reset_index(drop=True)
        print(f"  随机采样: {len(df):,} 行")
    return df


# ══════════════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════════════
def load_yelp(sample: int = 3000):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        df_raw = _load_via_hf_parquet(sample)
    except Exception as e:
        print(f"\n加载失败: {e}")
        print("请检查网络，或用 --local 指定本地已下载的 CSV 文件")
        sys.exit(1)
    _convert_and_save(df_raw)


def load_yelp_csv(csv_path: str, sample: int = 3000):
    """从本地已下载的 yelp_train.csv 加载（离线备用）"""
    print(f"从本地文件加载: {csv_path}")
    chunks, total = [], 0
    for chunk in pd.read_csv(csv_path, chunksize=2000,
                              on_bad_lines="skip", low_memory=False):
        chunks.append(chunk)
        total += len(chunk)
        if total >= sample * 2:
            break
    df = pd.concat(chunks, ignore_index=True).dropna(subset=["text", "stars_y"])
    df = df.sample(n=min(sample, len(df)), random_state=42).reset_index(drop=True)
    print(f"本地加载: {len(df)} 条")
    _convert_and_save(df)


# ── 字段转换 & 保存 ──────────────────────────────────────────
def _convert_and_save(df_raw: pd.DataFrame):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    reviews    = []
    shops_dict = {}

    for _, row in df_raw.iterrows():
        stars_y   = float(row.get("stars_y", 3) or 3)
        sentiment, label = _sentiment(stars_y)

        shop_id   = str(row.get("business_id", ""))
        shop_name = str(row.get("name", "Unknown"))
        city      = str(row.get("city", ""))
        state     = str(row.get("state", ""))
        cats      = str(row.get("categories", ""))
        category  = _category(cats)
        text      = str(row.get("text", ""))
        date_raw  = str(row.get("date", ""))

        try:
            review_time = pd.to_datetime(date_raw).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            review_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        review_id = hashlib.md5(
            f"{shop_id}{row.get('user_id','')}{date_raw}".encode()
        ).hexdigest()[:16]

        reviews.append({
            "review_id":       review_id,
            "shop_id":         shop_id,
            "shop_name":       shop_name,
            "platform":        "yelp",
            "category":        category,
            "city":            city,
            "district":        state,
            "user_id":         str(row.get("user_id", "")),
            "username":        str(row.get("user_id", ""))[:8],
            "user_level":      3,
            "vip_status":      False,
            "review_content":  text,
            "review_score":    stars_y,
            "score_text":      f"stars:{stars_y}",
            "review_time":     review_time,
            "like_count":      int(row.get("useful", 0) or 0),
            "reply_count":     int(row.get("funny",  0) or 0),
            "order_type":      "dine-in",
            "dishes":          "",
            "images":          "",
            "sentiment_label": label,
            "sentiment":       sentiment,
            "absa_aspects":    _absa(text, sentiment),
            "crawl_time":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        if shop_id not in shops_dict:
            shops_dict[shop_id] = {
                "shop_id":           shop_id,
                "shop_name":         shop_name,
                "platform":          "yelp",
                "category":          category,
                "city":              city,
                "district":          state,
                "address":           str(row.get("address", "")),
                "average_price":     0,
                "score":             float(row.get("stars_x", 0) or 0),
                "taste_score":       0,
                "environment_score": 0,
                "service_score":     0,
                "review_count":      int(row.get("review_count", 0) or 0),
                "tags":              cats[:100],
            }

    # 保存评论 CSV
    rev_fields = [
        "review_id","shop_id","shop_name","platform","category","city","district",
        "user_id","username","user_level","vip_status",
        "review_content","review_score","score_text","review_time",
        "like_count","reply_count","order_type","dishes","images",
        "sentiment_label","sentiment","absa_aspects","crawl_time",
    ]
    with open(REVIEWS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rev_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(reviews)

    # 保存店铺 CSV
    shops       = list(shops_dict.values())
    shop_fields = [
        "shop_id","shop_name","platform","category","city","district",
        "address","average_price","score","taste_score","environment_score",
        "service_score","review_count","tags",
    ]
    with open(SHOPS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=shop_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(shops)

    pos    = sum(1 for r in reviews if r["sentiment"] == "positive")
    neg    = sum(1 for r in reviews if r["sentiment"] == "negative")
    neu    = sum(1 for r in reviews if r["sentiment"] == "neutral")
    cities = len({r["city"] for r in reviews if r["city"]})

    print("\nYelp 数据转换完成")
    print(f"  评论总数: {len(reviews)}")
    print(f"  店铺数量: {len(shops)} 家 / {cities} 个城市")
    print(f"  情感分布: 正面 {pos}  负面 {neg}  中性 {neu}")
    print(f"  输出: {REVIEWS_CSV}")
    print(f"        {SHOPS_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="加载 Yelp 数据集")
    parser.add_argument("--sample", type=int, default=30000, help="采样条数")
    parser.add_argument("--local",  type=str, default="",   help="本地 CSV 路径")
    args = parser.parse_args()

    if args.local and os.path.exists(args.local):
        load_yelp_csv(args.local, sample=args.sample)
    else:
        load_yelp(sample=args.sample)

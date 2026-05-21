# -*- coding: utf-8 -*-
"""
Part 4-② 非结构化文本数据
功能：关键词提取 / 评论维度分析 / BERT & ABSA 训练集构建
"""

import re
import json
import os
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd

# 停用词（餐饮场景）
STOP_WORDS = {
    "的","了","是","在","我","有","和","就","都","而","着","或","没有",
    "感觉","觉得","非常","真的","一个","这","那","也","太","挺","比较",
    "有点","下次","来","不错","还是","就是","这里","这家","一些","大家",
}

# 餐饮五大维度
DIMENSIONS = {
    "口味": ["味道","口味","好吃","香","辣","甜","咸","鲜","嫩","脆","腻","淡","正宗","新鲜","入味","麻辣","鲜香"],
    "环境": ["环境","装修","氛围","卫生","干净","整洁","嘈杂","安静","舒适","拥挤","停车","空间","座位"],
    "服务": ["服务","态度","速度","等待","上菜","热情","周到","冷漠","催","慢","专业","礼貌","耐心"],
    "价格": ["价格","消费","性价比","便宜","贵","实惠","划算","值","优惠","折扣","人均","套餐"],
    "食材": ["食材","新鲜","新鲜度","质量","分量","份量","够","少","多","大","小"],
}


class TextAnalyzer:
    """文本数据分析器"""

    def _tokenize(self, text: str) -> list:
        if not isinstance(text, str):
            return []
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z]", " ", text)
        try:
            import jieba
            tokens = list(jieba.cut(text, cut_all=False))
        except ImportError:
            tokens = text.split()
        return [t for t in tokens if len(t) >= 2 and t not in STOP_WORDS and not t.isdigit()]

    # ── 1. 维度覆盖率 ────────────────────────────────────────
    def dimension_coverage(self, df: pd.DataFrame) -> pd.DataFrame:
        """各维度提及率与差评率"""
        records = []
        neg_mask = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce") == -1
        for dim, kws in DIMENSIONS.items():
            pat = "|".join(kws)
            hit = df["review_content"].fillna("").str.contains(pat, na=False)
            records.append({
                "维度":     dim,
                "提及数":   int(hit.sum()),
                "提及率%":  round(hit.mean() * 100, 1),
                "维度差评%": round((hit & neg_mask).sum() / max(hit.sum(), 1) * 100, 1),
            })
        return pd.DataFrame(records).sort_values("提及数", ascending=False)

    # ── 2. 词频统计 ──────────────────────────────────────────
    def word_frequency(self, df: pd.DataFrame,
                       sentiment: Optional[str] = None, top_n: int = 25) -> pd.DataFrame:
        """正/负/全部词频统计"""
        if sentiment and "sentiment" in df.columns:
            df = df[df["sentiment"] == sentiment]
        words = []
        for t in df["review_content"].dropna():
            words.extend(self._tokenize(str(t)))
        return pd.DataFrame(Counter(words).most_common(top_n), columns=["词语", "频次"])

    # ── 3. 差评信号词 ────────────────────────────────────────
    def neg_signal_words(self, df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """差评中高度集中的关键词"""
        neg = df[pd.to_numeric(df.get("sentiment_label", 0), errors="coerce") == -1]
        pos = df[pd.to_numeric(df.get("sentiment_label", 0), errors="coerce") == 1]
        nf, pf = Counter(), Counter()
        for t in neg["review_content"].dropna(): nf.update(self._tokenize(str(t)))
        for t in pos["review_content"].dropna(): pf.update(self._tokenize(str(t)))
        tn, tp = max(len(neg), 1), max(len(pos), 1)
        rows = [{"词语": w, "差评频次": c, "差评特有度": round(c/tn - pf.get(w,0)/tp, 4)}
                for w, c in nf.most_common(top_n * 3)]
        res = pd.DataFrame(rows).nlargest(top_n, "差评特有度")
        res["风险"] = pd.cut(res["差评特有度"], bins=[-np.inf,0,0.02,0.05,np.inf],
                             labels=["低","中","高","极高"])
        return res.reset_index(drop=True)

    # ── 4. 店铺特色词 ────────────────────────────────────────
    def shop_keywords(self, df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
        """每家店铺的高频特色词"""
        rows = []
        for sid, grp in df.groupby("shop_id"):
            name = grp["shop_name"].iloc[0] if "shop_name" in grp.columns else sid
            words = []
            for t in grp["review_content"].dropna():
                words.extend(self._tokenize(str(t)))
            for word, cnt in Counter(words).most_common(top_n):
                rows.append({"shop_id": sid, "店铺": name, "特色词": word, "频次": cnt})
        return pd.DataFrame(rows)

    # ── 5. BERT 训练集 ───────────────────────────────────────
    def build_bert_dataset(self, df: pd.DataFrame,
                           train=0.7, val=0.15, min_len=10) -> dict:
        """构建情感分类三元数据集"""
        LABEL = {1: "positive", 0: "neutral", -1: "negative"}
        df = df.copy()
        df["sentiment_label"] = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce")
        valid = df[
            df["review_content"].fillna("").str.len() >= min_len
            & df["sentiment_label"].isin([1, 0, -1])
        ].copy()
        valid["label"] = valid["sentiment_label"].map(LABEL)
        valid = valid.sample(frac=1, random_state=42).reset_index(drop=True)
        n = len(valid)
        n_tr = int(n * train)
        n_va = int(n * val)
        def _subset(sdf):
            return sdf[["review_content","label","shop_id","platform"]].rename(
                columns={"review_content":"text"})
        dataset = {
            "train": _subset(valid.iloc[:n_tr]),
            "val":   _subset(valid.iloc[n_tr:n_tr+n_va]),
            "test":  _subset(valid.iloc[n_tr+n_va:]),
        }
        print(f"[BERT] train={len(dataset['train'])} val={len(dataset['val'])} test={len(dataset['test'])}")
        return dataset

    def save_bert_dataset(self, dataset: dict, out_dir: str = "outputs/datasets"):
        """导出 JSONL 格式"""
        os.makedirs(out_dir, exist_ok=True)
        for split, sdf in dataset.items():
            path = os.path.join(out_dir, f"bert_{split}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for _, row in sdf.iterrows():
                    f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
            print(f"  -> {path} ({len(sdf)} 条)")

    # ── 6. ABSA 数据集 ───────────────────────────────────────
    def build_absa_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 absa_aspects 字段构建细粒度情感数据集"""
        rows = []
        for _, row in df.iterrows():
            text = row.get("review_content", "")
            raw  = row.get("absa_aspects", "")
            if not text or not raw:
                continue
            try:
                aspects = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            if not isinstance(aspects, list):
                continue
            for a in aspects:
                if isinstance(a, dict) and a.get("aspect"):
                    rows.append({
                        "text":      text,
                        "aspect":    a.get("aspect",""),
                        "opinion":   a.get("opinion",""),
                        "sentiment": row.get("sentiment","neutral"),
                        "shop_id":   row.get("shop_id",""),
                    })
        result = pd.DataFrame(rows)
        print(f"[ABSA] {len(result)} 条 aspect 样本，来自 {result['text'].nunique()} 条评论")
        return result

    def save_absa_pyabsa(self, df: pd.DataFrame, path: str = "outputs/datasets/absa_train.txt"):
        """导出 PyABSA 格式"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lmap = {"positive":"Positive","neutral":"Neutral","negative":"Negative"}
        with open(path, "w", encoding="utf-8") as f:
            for _, r in df.iterrows():
                f.write(f"{r['text']}${lmap.get(r['sentiment'],'Neutral')}${r['aspect']}\n")
        print(f"[ABSA] PyABSA 格式 -> {path} ({len(df)} 条)")

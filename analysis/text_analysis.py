# -*- coding: utf-8 -*-
"""
Part 4-② 非结构化文本数据
功能: 关键词提取 / 评论维度分析 / BERT & ABSA 训练集构建
支持: 英文文本 (Yelp 数据集) 及中文文本 (旧版合成数据)
"""

import re
import json
import os
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd

# ── 英文停用词（餐饮场景）────────────────────────────────────
EN_STOP_WORDS = {
    "i","me","my","we","our","you","your","he","she","they","them",
    "the","a","an","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could","should",
    "at","in","on","to","of","for","with","from","by","about","as",
    "this","that","these","those","it","its","and","or","but","not",
    "so","if","there","here","what","when","where","how","which","who",
    "just","also","very","really","quite","more","most","much","many",
    "some","any","all","both","each","few","same","other","than","only",
    "then","than","now","too","well","back","still","even","get","got",
    "one","two","time","go","going","came","come","went","said","say",
}

# 中文停用词（兼容旧数据）
ZH_STOP_WORDS = {
    "的","了","是","在","我","有","和","就","都","而","着","或","没有",
    "感觉","觉得","非常","真的","一个","这","那","也","太","挺","比较",
    "有点","下次","来","不错","还是","就是","这里","这家","一些","大家",
}

# ── 英文餐饮维度 ─────────────────────────────────────────────
EN_DIMENSIONS = {
    "Food":     ["food","taste","flavor","delicious","bland","fresh","stale","portion",
                 "dish","meal","menu","cuisine","cooking","seasoning","ingredient"],
    "Service":  ["service","staff","waiter","waitress","server","host","rude","friendly",
                 "slow","attentive","helpful","professional","courtesy","recommend"],
    "Ambiance": ["ambiance","atmosphere","decor","noise","noisy","clean","dirty","cozy",
                 "crowded","busy","quiet","comfortable","dark","bright","interior","setting"],
    "Price":    ["price","expensive","cheap","value","overpriced","affordable","worth",
                 "bill","cost","money","reasonable","pricey","deal","tip"],
    "Location": ["location","parking","convenient","far","close","accessible","neighborhood",
                 "drive","walk","distance","downtown","area"],
}

# 中文维度（兼容）
ZH_DIMENSIONS = {
    "口味": ["味道","口味","好吃","香","辣","甜","咸","鲜","嫩","脆","腻","淡","正宗","新鲜"],
    "环境": ["环境","装修","氛围","卫生","干净","整洁","嘈杂","安静","舒适","拥挤","座位"],
    "服务": ["服务","态度","速度","等待","上菜","热情","周到","冷漠","慢","专业","礼貌"],
    "价格": ["价格","消费","性价比","便宜","贵","实惠","划算","值","优惠","人均"],
    "食材": ["食材","新鲜","质量","分量","份量","大","小"],
}


def _detect_lang(df: pd.DataFrame) -> str:
    """自动检测数据语言: 'en' 或 'zh'"""
    sample = " ".join(df["review_content"].dropna().head(10).tolist())
    zh_count = len(re.findall(r"[\u4e00-\u9fa5]", sample))
    return "zh" if zh_count > len(sample) * 0.3 else "en"


class TextAnalyzer:
    """文本数据分析器（自动适配中英文）"""

    def __init__(self, lang: Optional[str] = None):
        """
        lang: 'en' / 'zh' / None(自动检测)
        """
        self._lang = lang

    def _get_lang(self, df: pd.DataFrame) -> str:
        return self._lang or _detect_lang(df)

    def _get_dims(self, lang: str) -> dict:
        return EN_DIMENSIONS if lang == "en" else ZH_DIMENSIONS

    def _tokenize(self, text: str, lang: str) -> list:
        if not isinstance(text, str):
            return []
        if lang == "en":
            tokens = re.findall(r"[a-zA-Z']+", text.lower())
            return [t for t in tokens if len(t) >= 3 and t not in EN_STOP_WORDS]
        else:
            text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z]", " ", text)
            try:
                import jieba
                tokens = list(jieba.cut(text, cut_all=False))
            except ImportError:
                tokens = text.split()
            return [t for t in tokens if len(t) >= 2 and t not in ZH_STOP_WORDS]

    # ── 1. 维度覆盖率 ────────────────────────────────────────
    def dimension_coverage(self, df: pd.DataFrame) -> pd.DataFrame:
        """各维度提及率与差评率"""
        lang = self._get_lang(df)
        dims = self._get_dims(lang)
        neg_mask = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce") == -1
        records = []
        for dim, kws in dims.items():
            pat = r"\b(" + "|".join(kws) + r")\b" if lang == "en" else "|".join(kws)
            hit = df["review_content"].fillna("").str.lower().str.contains(pat, na=False, regex=True)
            records.append({
                "dimension" if lang == "en" else "维度": dim,
                "mentions":  int(hit.sum()),
                "mention%":  round(hit.mean() * 100, 1),
                "neg_in_dim%": round((hit & neg_mask).sum() / max(hit.sum(), 1) * 100, 1),
            })
        res = pd.DataFrame(records).sort_values("mentions", ascending=False)
        return res.reset_index(drop=True)

    # ── 2. 词频统计 ──────────────────────────────────────────
    def word_frequency(self, df: pd.DataFrame,
                       sentiment: Optional[str] = None, top_n: int = 25) -> pd.DataFrame:
        """正/负/全部词频统计"""
        lang = self._get_lang(df)
        if sentiment and "sentiment" in df.columns:
            df = df[df["sentiment"] == sentiment]
        words = []
        for t in df["review_content"].dropna():
            words.extend(self._tokenize(str(t), lang))
        col = "word" if lang == "en" else "词语"
        return pd.DataFrame(Counter(words).most_common(top_n), columns=[col, "count"])

    # ── 3. 差评信号词 ────────────────────────────────────────
    def neg_signal_words(self, df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """差评中高度集中的关键词"""
        lang = self._get_lang(df)
        label_col = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce")
        neg = df[label_col == -1]
        pos = df[label_col ==  1]
        nf, pf = Counter(), Counter()
        for t in neg["review_content"].dropna(): nf.update(self._tokenize(str(t), lang))
        for t in pos["review_content"].dropna(): pf.update(self._tokenize(str(t), lang))
        tn, tp = max(len(neg), 1), max(len(pos), 1)
        word_col = "word" if lang == "en" else "词语"
        rows = [{word_col: w,
                 "neg_count": c,
                 "neg_score": round(c/tn - pf.get(w, 0)/tp, 4)}
                for w, c in nf.most_common(top_n * 3)]
        res = pd.DataFrame(rows).nlargest(top_n, "neg_score")
        res["risk"] = pd.cut(res["neg_score"], bins=[-np.inf, 0, 0.02, 0.05, np.inf],
                             labels=["low", "medium", "high", "critical"])
        return res.reset_index(drop=True)

    # ── 4. 店铺特色词 ────────────────────────────────────────
    def shop_keywords(self, df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
        """每家店铺的高频特色词"""
        lang = self._get_lang(df)
        rows = []
        for sid, grp in df.groupby("shop_id"):
            name = grp["shop_name"].iloc[0] if "shop_name" in grp.columns else sid
            words = []
            for t in grp["review_content"].dropna():
                words.extend(self._tokenize(str(t), lang))
            word_col = "keyword" if lang == "en" else "特色词"
            for word, cnt in Counter(words).most_common(top_n):
                rows.append({"shop_id": sid, "shop_name": name, word_col: word, "count": cnt})
        return pd.DataFrame(rows)

    # ── 5. 评论长度分布 ──────────────────────────────────────
    def review_length_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """按情感分组的评论长度统计"""
        df = df.copy()
        df["content_len"] = df["review_content"].fillna("").str.len()
        return (df.groupby("sentiment")["content_len"]
                  .agg(count="count", mean="mean", median="median",
                       p25=lambda x: x.quantile(0.25),
                       p75=lambda x: x.quantile(0.75))
                  .round(1)
                  .reset_index())

    # ── 6. BERT 训练集 ───────────────────────────────────────
    def build_bert_dataset(self, df: pd.DataFrame,
                           train: float = 0.7, val: float = 0.15,
                           min_len: int = 20) -> dict:
        """构建情感分类三分数据集"""
        LABEL = {1: "positive", 0: "neutral", -1: "negative"}
        df = df.copy()
        df["sentiment_label"] = pd.to_numeric(df.get("sentiment_label", 0), errors="coerce")
        valid = df[
            (df["review_content"].fillna("").str.len() >= min_len) &
            (df["sentiment_label"].isin([1, 0, -1]))
        ].copy()
        valid["label"] = valid["sentiment_label"].map(LABEL)
        valid = valid.sample(frac=1, random_state=42).reset_index(drop=True)
        n = len(valid)
        n_tr = int(n * train)
        n_va = int(n * val)
        def _subset(sdf):
            return sdf[["review_content", "label", "shop_id", "platform"]].rename(
                columns={"review_content": "text"})
        dataset = {
            "train": _subset(valid.iloc[:n_tr]),
            "val":   _subset(valid.iloc[n_tr:n_tr + n_va]),
            "test":  _subset(valid.iloc[n_tr + n_va:]),
        }
        print(f"[BERT] train={len(dataset['train'])} / val={len(dataset['val'])} / test={len(dataset['test'])}")
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

    # ── 7. LDA 主题建模 ──────────────────────────────────────
    def topic_modeling(self, df: pd.DataFrame,
                       n_topics: int = 8, n_words: int = 10) -> pd.DataFrame:
        """
        LDA 隐含狄利克雷分布主题建模。
        英文使用 sklearn CountVectorizer（stop_words='english'）；
        中文使用 jieba 分词后构建词袋。
        返回每个主题的 top_words、主导评论数和占比。
        """
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer

        lang = self._get_lang(df)
        texts = df["review_content"].fillna("").tolist()

        if lang == "en":
            vec = CountVectorizer(
                max_df=0.9, min_df=5, max_features=3000,
                stop_words="english",
                token_pattern=r"[a-zA-Z]{3,}"
            )
            corpus = texts
        else:
            def _zh_join(t):
                try:
                    import jieba
                    tokens = [w for w in jieba.cut(t)
                              if len(w) >= 2 and w not in ZH_STOP_WORDS]
                except ImportError:
                    tokens = [w for w in t.split()
                              if len(w) >= 2 and w not in ZH_STOP_WORDS]
                return " ".join(tokens)
            corpus = [_zh_join(t) for t in texts]
            vec = CountVectorizer(max_df=0.9, min_df=5, max_features=3000)

        X     = vec.fit_transform(corpus)
        vocab = vec.get_feature_names_out()

        lda = LatentDirichletAllocation(
            n_components=n_topics, max_iter=30, random_state=42,
            learning_method="online", learning_offset=50.0
        )
        lda.fit(X)

        topic_doc     = lda.transform(X)            # (n_samples, n_topics)
        dominant      = topic_doc.argmax(axis=1)

        rows = []
        for t_idx, comp in enumerate(lda.components_):
            top_w = [vocab[i] for i in comp.argsort()[-n_words:][::-1]]
            cnt   = int((dominant == t_idx).sum())
            rows.append({
                "topic_id":    t_idx,
                "top_words":   ", ".join(top_w),
                "review_count": cnt,
                "proportion":  round(cnt / max(len(df), 1) * 100, 1),
            })
        return (pd.DataFrame(rows)
                .sort_values("review_count", ascending=False)
                .reset_index(drop=True))

    # ── 8. TF-IDF + 逻辑回归情感分类器 ──────────────────────
    def sentiment_classifier(self, df: pd.DataFrame,
                              test_size: float = 0.2) -> dict:
        """
        在本地训练并评估 TF-IDF（1-2gram）+ 逻辑回归情感分类器。
        特征：sublinear TF-IDF，max_features=8000；
        模型：class_weight='balanced' 的多分类逻辑回归。
        返回字典含 accuracy / classification_report / model / vectorizer
        / train_size / test_size，可直接用于推理或导出。
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, classification_report
        from sklearn.model_selection import train_test_split

        lang      = self._get_lang(df)
        label_col = pd.to_numeric(df.get("sentiment_label",
                                         pd.Series(dtype=float)),
                                  errors="coerce")
        valid = df[label_col.isin([1, 0, -1])].copy()
        valid["_label"] = label_col[valid.index].astype(int)
        valid = valid.dropna(subset=["review_content", "_label"])

        X_raw = valid["review_content"].fillna("").tolist()
        y     = valid["_label"].tolist()

        X_tr, X_te, y_tr, y_te = train_test_split(
            X_raw, y, test_size=test_size, random_state=42, stratify=y
        )

        pattern = r"[a-zA-Z]{3,}" if lang == "en" else r"\S+"
        tfidf = TfidfVectorizer(
            max_features=8000, ngram_range=(1, 2),
            min_df=3, sublinear_tf=True, token_pattern=pattern
        )
        X_tr_v = tfidf.fit_transform(X_tr)
        X_te_v = tfidf.transform(X_te)

        clf = LogisticRegression(
            C=1.0, max_iter=1000, class_weight="balanced",
            solver="lbfgs", multi_class="auto", random_state=42
        )
        clf.fit(X_tr_v, y_tr)
        y_pred = clf.predict(X_te_v)

        report = classification_report(
            y_te, y_pred,
            target_names=["Negative(-1)", "Neutral(0)", "Positive(1)"],
            output_dict=True
        )
        print(f"[分类器] 准确率: {accuracy_score(y_te, y_pred):.4f}  "
              f"训练={len(X_tr)}  测试={len(X_te)}")
        return {
            "accuracy":    round(accuracy_score(y_te, y_pred), 4),
            "report":      report,
            "model":       clf,
            "vectorizer":  tfidf,
            "train_size":  len(X_tr),
            "test_size":   len(X_te),
        }

    # ── 9. 维度-情感矩阵 ─────────────────────────────────────
    def aspect_sentiment_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        各服务维度正 / 中 / 负评论比例矩阵（可直接用于热力图）。
        行 = 维度，列 = positive_pct / neutral_pct / negative_pct / total_mentions。
        """
        lang      = self._get_lang(df)
        dims      = self._get_dims(lang)
        label_col = pd.to_numeric(
            df.get("sentiment_label", 0), errors="coerce"
        )
        rows = []
        for dim, kws in dims.items():
            pat = (r"\b(" + "|".join(kws) + r")\b"
                   if lang == "en" else "|".join(kws))
            hit = (df["review_content"].fillna("")
                   .str.lower()
                   .str.contains(pat, na=False, regex=True))
            sub   = label_col[hit]
            total = max(len(sub), 1)
            rows.append({
                "dimension":    dim,
                "positive_pct": round((sub == 1).sum()  / total * 100, 1),
                "neutral_pct":  round((sub == 0).sum()  / total * 100, 1),
                "negative_pct": round((sub == -1).sum() / total * 100, 1),
                "total_mentions": int(hit.sum()),
            })
        return pd.DataFrame(rows).sort_values("total_mentions", ascending=False)

    # ── 10. ABSA 数据集 ──────────────────────────────────────
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
                        "aspect":    a.get("aspect", ""),
                        "sentiment": row.get("sentiment", "neutral"),
                        "shop_id":   row.get("shop_id", ""),
                        "stars":     row.get("review_score", 3),
                    })
        result = pd.DataFrame(rows)
        if not result.empty:
            print(f"[ABSA] {len(result)} 条 aspect 样本，来自 {result['text'].nunique()} 条评论")
        return result

    def save_absa_pyabsa(self, df: pd.DataFrame,
                         path: str = "outputs/datasets/absa_train.txt"):
        """导出 PyABSA 格式"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lmap = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
        with open(path, "w", encoding="utf-8") as f:
            for _, r in df.iterrows():
                f.write(f"{r['text']}${lmap.get(r['sentiment'], 'Neutral')}${r['aspect']}\n")
        print(f"[ABSA] PyABSA 格式 -> {path} ({len(df)} 条)")

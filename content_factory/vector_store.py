# -*- coding: utf-8 -*-
"""
模块5：向量知识库 + 自动摘要提取
- 轻量级本地向量方案：TF-IDF + 余弦相似度（无需额外数据库/模型下载）
- 文档向量化、持久化存储
- 语义检索接口，查询相关行业资料
- 自动摘要：TF-IDF 关键句抽取
- 预留 sentence-transformers 升级接口（配置项）
"""
import os
import json
import pickle
import re
import datetime
from config_loader import VECTOR_DB_DIR, DATA_DIR

VECTORS_FILE = os.path.join(VECTOR_DB_DIR, "vectors.pkl")
META_FILE = os.path.join(VECTOR_DB_DIR, "meta.json")
FEATURES_FILE = os.path.join(VECTOR_DB_DIR, "tfidf_features.pkl")

_storage = {"matrix": None, "meta": [], "vectorizer": None}


def _load_storage():
    if _storage["meta"]:
        return
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            _storage["meta"] = json.load(f)
    if os.path.exists(VECTORS_FILE):
        with open(VECTORS_FILE, "rb") as f:
            data = pickle.load(f)
            _storage["matrix"] = data.get("matrix")
            _storage["vectorizer"] = data.get("vectorizer")


def _save():
    with open(VECTORS_FILE, "wb") as f:
        pickle.dump({"matrix": _storage["matrix"], "vectorizer": _storage["vectorizer"]}, f)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(_storage["meta"], f, ensure_ascii=False, indent=2)


def _to_features(text: str) -> list:
    """中文分词（简易：按字/标点切短语）"""
    tokens = re.findall(r"[\u4e00-\u9fa5]{2,}|[A-Za-z]+|\d+", text)
    return " ".join(tokens)


def index_document(doc_id: str, title: str, content: str, tags: list = None, source: str = ""):
    """文档向量化入库"""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from scipy import sparse
    _load_storage()
    text_feat = _to_features(title + " " + content)
    # 已存在则更新
    _storage["meta"] = [m for m in _storage["meta"] if m["doc_id"] != doc_id]
    _storage["meta"].append({
        "doc_id": doc_id, "title": title, "tags": tags or [],
        "source": source, "ts": datetime.datetime.now().isoformat(),
        "text_feat": text_feat
    })
    texts = [m["text_feat"] for m in _storage["meta"]]
    vec = TfidfVectorizer()
    matrix = vec.fit_transform(texts)
    _storage["matrix"] = matrix
    _storage["vectorizer"] = vec
    _save()


def search(query: str, topk: int = 5) -> list:
    """语义检索，返回最相关文档"""
    _load_storage()
    if not _storage["meta"] or _storage["matrix"] is None:
        return []
    from sklearn.metrics.pairwise import cosine_similarity
    q_feat = _to_features(query)
    q_vec = _storage["vectorizer"].transform([q_feat])
    sims = cosine_similarity(q_vec, _storage["matrix"]).flatten()
    ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:topk]
    result = []
    for idx, score in ranked:
        m = _storage["meta"][idx]
        if score > 0.001:
            result.append({
                "doc_id": m["doc_id"], "title": m["title"],
                "score": round(float(score), 4), "tags": m["tags"], "source": m["source"]
            })
    return result


def auto_summary(content: str, max_sentences: int = 3) -> str:
    """自动摘要：按句子 TF-IDF 权重抽取核心要点"""
    sentences = re.split(r"[。！？\.\!\?\n]+", content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    if not sentences:
        return content[:200]
    from sklearn.feature_extraction.text import TfidfVectorizer
    try:
        vec = TfidfVectorizer()
        m = vec.fit_transform([_to_features(s) for s in sentences])
        scores = m.sum(axis=1).A1
        ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
        ranked.sort()
        return "；".join(sentences[i] for i in ranked)
    except Exception:
        return "".join(sentences[:max_sentences])


def list_indexed():
    _load_storage()
    return [{"doc_id": m["doc_id"], "title": m["title"], "tags": m["tags"],
             "source": m["source"], "ts": m["ts"]} for m in _storage["meta"]]


if __name__ == "__main__":
    # 自检
    index_document("demo1", "MCP协议实战教程", "本文讲解MCP协议搭建智能体的完整流程，含代码示例与调试技巧。", ["MCP","智能体"])
    print("摘要:", auto_summary("MCP协议是模型上下文协议。本文讲解MCP协议搭建智能体的完整流程。含代码示例与调试技巧。"))
    print("检索:", search("MCP智能体"))

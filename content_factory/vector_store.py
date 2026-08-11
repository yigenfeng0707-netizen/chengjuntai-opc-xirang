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

# 检测 sklearn 是否可用（缺失时所有 TF-IDF 操作降级为关键词匹配）
try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401
    from sklearn.metrics.pairwise import cosine_similarity  # noqa: F401
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


def _load_storage():
    if _storage["meta"]:
        return
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                _storage["meta"] = json.load(f)
        except (json.JSONDecodeError, OSError):
            _storage["meta"] = []
    if os.path.exists(VECTORS_FILE):
        try:
            with open(VECTORS_FILE, "rb") as f:
                data = pickle.load(f)
                _storage["matrix"] = data.get("matrix")
                _storage["vectorizer"] = data.get("vectorizer")
        except Exception:
            # pickle 反序列化可能因 sklearn/scipy 缺失或版本变更而失败，降级为空
            _storage["matrix"] = None
            _storage["vectorizer"] = None


def _save():
    # 仅当有有效的 sklearn 矩阵时才保存 vectors.pkl，避免保存 None 导致后续 pickle 恢复问题
    if _storage["matrix"] is not None and _storage["vectorizer"] is not None:
        try:
            with open(VECTORS_FILE, "wb") as f:
                pickle.dump({"matrix": _storage["matrix"], "vectorizer": _storage["vectorizer"]}, f)
        except Exception:
            pass  # 序列化失败不阻塞主流程
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(_storage["meta"], f, ensure_ascii=False, indent=2)


def _to_features(text: str) -> list:
    """中文分词（简易：按字/标点切短语）"""
    tokens = re.findall(r"[\u4e00-\u9fa5]{2,}|[A-Za-z]+|\d+", text)
    return " ".join(tokens)


def index_document(doc_id: str, title: str, content: str, tags: list = None, source: str = ""):
    """文档向量化入库；sklearn 缺失时降级为仅存元数据（检索退化为关键词匹配）。"""
    _load_storage()
    text_feat = _to_features(title + " " + content)
    # 已存在则更新
    _storage["meta"] = [m for m in _storage["meta"] if m["doc_id"] != doc_id]
    _storage["meta"].append({
        "doc_id": doc_id, "title": title, "tags": tags or [],
        "source": source, "ts": datetime.datetime.now().isoformat(),
        "text_feat": text_feat
    })
    if _HAS_SKLEARN:
        try:
            from scipy import sparse  # noqa: F401
            texts = [m["text_feat"] for m in _storage["meta"]]
            vec = TfidfVectorizer()
            matrix = vec.fit_transform(texts)
            _storage["matrix"] = matrix
            _storage["vectorizer"] = vec
        except Exception:
            _storage["matrix"] = None
            _storage["vectorizer"] = None
    else:
        _storage["matrix"] = None
        _storage["vectorizer"] = None
    _save()


def search(query: str, topk: int = 5) -> list:
    """语义检索，返回最相关文档；sklearn 缺失时降级为关键词重叠匹配。"""
    _load_storage()
    if not _storage["meta"]:
        return []
    # 降级路径：关键词重叠匹配
    if not _HAS_SKLEARN or _storage["matrix"] is None or _storage["vectorizer"] is None:
        q_tokens = set(_to_features(query).split())
        scored = []
        for i, m in enumerate(_storage["meta"]):
            doc_tokens = set(m.get("text_feat", "").split())
            overlap = len(q_tokens & doc_tokens)
            if overlap > 0:
                scored.append((i, overlap / max(1, len(q_tokens))))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = []
        for idx, score in scored[:topk]:
            m = _storage["meta"][idx]
            result.append({
                "doc_id": m["doc_id"], "title": m["title"],
                "score": round(float(score), 4), "tags": m["tags"], "source": m["source"]
            })
        return result
    # sklearn 路径：TF-IDF 余弦相似度
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
    """自动摘要：按句子 TF-IDF 权重抽取核心要点；sklearn 缺失时降级为前 N 句拼接。"""
    sentences = re.split(r"[。！？\.\!\?\n]+", content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    if not sentences:
        return content[:200]
    # 降级实现：无 sklearn 时按句子长度+位置加权抽取
    def _fallback_summary():
        # 优先取较长且靠前的句子（信息密度通常更高）
        scored = [(i, len(s), s) for i, s in enumerate(sentences)]
        scored.sort(key=lambda x: (-x[1], x[0]))  # 长句优先，同长取靠前
        picked = sorted(scored[:max_sentences], key=lambda x: x[0])  # 恢复原文顺序
        return "；".join(s for _, _, s in picked)
    if not _HAS_SKLEARN:
        return _fallback_summary()
    try:
        vec = TfidfVectorizer()
        m = vec.fit_transform([_to_features(s) for s in sentences])
        scores = m.sum(axis=1).A1
        ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
        ranked.sort()
        return "；".join(sentences[i] for i in ranked)
    except Exception:
        return _fallback_summary()


def list_indexed():
    _load_storage()
    return [{"doc_id": m["doc_id"], "title": m["title"], "tags": m["tags"],
             "source": m["source"], "ts": m["ts"]} for m in _storage["meta"]]


if __name__ == "__main__":
    # 自检
    index_document("demo1", "MCP协议实战教程", "本文讲解MCP协议搭建智能体的完整流程，含代码示例与调试技巧。", ["MCP","智能体"])
    print("摘要:", auto_summary("MCP协议是模型上下文协议。本文讲解MCP协议搭建智能体的完整流程。含代码示例与调试技巧。"))
    print("检索:", search("MCP智能体"))

"""
高级检索管线：HyDE + BM25 + 云端 Rerank 精排
"""
import os
import json
import numpy as np
from typing import Sequence
from collections import defaultdict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from utils.logger_handler import logger
from utils.config_handler import rag_conf
from models.factory import chat_model, embed_model
import urllib.request

# HyDE 提示词
HYDE_PROMPT = PromptTemplate.from_template(
    "根据以下问题，写一段简短的专业文档来回答它（50-200字）：\n{query}"
)

# BM25
try:
    from rank_bm25 import BM25Okapi
    _bm25_available = True
except ImportError:
    _bm25_available = False
    logger.warning("[高级检索] rank_bm25 未安装，跳过 BM25")


def _build_bm25(documents: Sequence[Document]):
    if not _bm25_available or not documents:
        return None, None
    try:
        try:
            import jieba
            corpus = [list(jieba.cut(doc.page_content)) for doc in documents]
        except ImportError:
            corpus = [doc.page_content.split() for doc in documents]
        texts = [doc.page_content for doc in documents]
        return texts, BM25Okapi(corpus)
    except Exception as e:
        logger.warning(f"[BM25] 构建失败: {e}")
        return None, None


def _dashscope_rerank(query: str, documents: list[Document], top_k: int = 3) -> list[Document]:
    """使用 DashScope gte-rerank 云端模型精排"""
    if not documents:
        return documents
    try:
        texts = [doc.page_content for doc in documents]
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")

        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        payload = {
            "model": rag_conf.get("rerank_model_name", "gte-rerank"),
            "input": {"query": query, "documents": texts},
            "parameters": {"top_n": min(top_k, len(texts))},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("output", {}).get("results", [])
        scored = sorted(results, key=lambda r: r.get("relevance_score", 0), reverse=True)
        return [documents[r["index"]] for r in scored[:top_k]]

    except Exception as e:
        logger.info(f"[Rerank] 云端精排不可用，使用融合结果: {e}")
        return documents[:top_k]


def _reciprocal_rank_fusion(results: list[list[Document]], k: int = 60) -> list[Document]:
    doc_scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, Document] = {}
    for result_list in results:
        for rank, doc in enumerate(result_list, 1):
            # 使用内容前100字符作为ID
            did = doc.page_content[:100]
            doc_scores[did] += 1.0 / (k + rank)
            doc_map[did] = doc
    sorted_ids = sorted(doc_scores, key=doc_scores.get, reverse=True)
    return [doc_map[did] for did in sorted_ids]


class AdvancedRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.hyde_chain = HYDE_PROMPT | chat_model | StrOutputParser()

    def _generate_hypothetical_doc(self, query: str) -> str:
        try:
            return self.hyde_chain.invoke({"query": query})
        except Exception as e:
            logger.warning(f"[HyDE] 生成失败，回退: {e}")
            return query

    def _semantic_search(self, query: str, user_id: int, k: int = 10) -> list[Document]:
        hyde_doc = self._generate_hypothetical_doc(query)
        vs = self.vector_store._get_vector_store(user_id)
        return vs.similarity_search(hyde_doc, k=k)

    def _keyword_search(self, query: str, user_id: int, k: int = 10) -> list[Document]:
        vs = self.vector_store._get_vector_store(user_id)
        all_docs = vs.get()
        if not all_docs or not all_docs["documents"]:
            return []
        documents = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(all_docs["documents"], all_docs["metadatas"])
        ]
        texts, bm25 = _build_bm25(documents)
        if not bm25:
            return []
        try:
            import jieba
            tokenized = list(jieba.cut(query))
        except ImportError:
            tokenized = query.split()
        scores = bm25.get_scores(tokenized)
        top_indices = np.argsort(scores)[-k:][::-1]
        return [documents[i] for i in top_indices if scores[i] > 0]

    def retrieve(self, query: str, user_id: int, final_k: int = 3) -> list[Document]:
        logger.info(f"[高级检索] query={query[:50]}... user={user_id}")

        semantic_docs = self._semantic_search(query, user_id, k=10)
        logger.info(f"[高级检索] 语义召回 {len(semantic_docs)} 条")

        keyword_docs = self._keyword_search(query, user_id, k=10)
        logger.info(f"[高级检索] 关键词召回 {len(keyword_docs)} 条")

        fused = _reciprocal_rank_fusion([semantic_docs, keyword_docs])
        logger.info(f"[高级检索] 融合后 {len(fused)} 条")

        reranked = _dashscope_rerank(query, fused, top_k=final_k)
        logger.info(f"[高级检索] 精排出 {len(reranked)} 条")

        return reranked

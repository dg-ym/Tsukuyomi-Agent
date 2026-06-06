"""
总结服务类：高级检索（HyDE + BM25 + RRF + CrossEncoder）→ LLM 总结回答
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.vector_store import vector_store
from rag.advanced_retriever import AdvancedRetriever
from utils.prompt_loader import load_rag_prompts
from models.factory import chat_model
from utils.context_vars import current_user_id


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = vector_store
        self.advanced_retriever = AdvancedRetriever(self.vector_store)
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query: str, user_id: int = None) -> list[Document]:
        """高级检索：HyDE + BM25 → RRF → CrossEncoder"""
        if user_id is None:
            user_id = current_user_id.get()
        if user_id is None:
            return []
        return self.advanced_retriever.retrieve(query, user_id)

    def rag_summarize(self, query: str, user_id: int = None) -> str:
        context_docs = self.retriever_docs(query, user_id)
        if not context_docs:
            return "未在您的知识库中找到相关信息。"

        context = ""
        for i, doc in enumerate(context_docs, 1):
            src = doc.metadata.get("source", doc.metadata.get("filename", "未知"))
            context += f"【参考资料{i}】(来源:{src}) {doc.page_content}\n"

        return self.chain.invoke({
            "input": query,
            "context": context
        })

    def summarize_history(self, messages: list[dict]) -> str:
        """对较早的历史消息做摘要，超过 20 条时注入上下文"""
        if not messages:
            return ""

        # 拼接对话记录
        history_text = ""
        for m in messages:
            role = "用户" if m["role"] == "user" else "助手"
            history_text += f"{role}: {m['content']}\n"

        prompt = (
            "你是一个对话摘要助手。请用 100-200 字简要总结以下历史对话的核心内容，"
            "保留关键事实、用户偏好和重要结论，忽略问候语和客套话。\n\n"
            f"对话记录:\n{history_text}\n\n摘要:"
        )

        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import PromptTemplate
            chain = PromptTemplate.from_template(prompt) | self.model | StrOutputParser()
            return chain.invoke({})
        except Exception as e:
            return f"(历史摘要生成失败: {e})"

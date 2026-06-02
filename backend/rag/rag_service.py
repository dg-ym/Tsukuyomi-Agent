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

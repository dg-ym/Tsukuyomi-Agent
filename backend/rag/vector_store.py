from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.config_handler import chroma_conf
from models.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.file_handler import get_file_documents
from utils.logger_handler import logger
from utils.context_vars import current_user_id

import os


class VectorStoreService:
    """支持多用户隔离的向量存储服务（单例）"""

    def __init__(self):
        self._persist_dir = chroma_conf["persist_directory"]
        self._spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def _get_collection_name(self, user_id: int) -> str:
        return f"kb_user_{user_id}"

    def _get_vector_store(self, user_id: int) -> Chroma:
        return Chroma(
            collection_name=self._get_collection_name(user_id),
            embedding_function=embed_model,
            persist_directory=self._persist_dir,
        )

    def add_document(self, user_id: int, file_content: list[Document], md5_hash: str) -> int:
        vs = self._get_vector_store(user_id)
        split_docs = self._spliter.split_documents(file_content)
        if not split_docs:
            logger.warning(f"[向量库]user={user_id} 文件分片后无有效内容，跳过")
            return 0
        vs.add_documents(split_docs)
        logger.info(f"[向量库]user={user_id} 存入 {len(split_docs)} 个分片")
        return len(split_docs)

    def delete_document(self, user_id: int, md5_hash: str) -> bool:
        vs = self._get_vector_store(user_id)
        try:
            results = vs.get(where={"md5_hash": md5_hash})
            if results and results["ids"]:
                vs.delete(ids=results["ids"])
                logger.info(f"[向量库]user={user_id} 删除MD5={md5_hash} 共 {len(results['ids'])} 条")
                return True
            return False
        except Exception as e:
            logger.error(f"[向量库]user={user_id} 删除失败: {e}")
            return False

    def load_from_content(self, user_id: int, content: bytes, filename: str, md5_hash: str) -> int:
        """从内存内容直接加载到向量库"""
        import tempfile
        ext = os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            tmp_path = tmp.name
        try:
            documents = get_file_documents(tmp_path)
            if not documents:
                return 0
            for doc in documents:
                doc.metadata["user_id"] = user_id
                doc.metadata["md5_hash"] = md5_hash
            return self.add_document(user_id, documents, md5_hash)
        finally:
            os.unlink(tmp_path)


# 全局单例
vector_store = VectorStoreService()

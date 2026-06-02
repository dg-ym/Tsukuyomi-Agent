import os
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader, PyPDFLoader, CSVLoader, Docx2txtLoader, UnstructuredExcelLoader,
    PyMuPDFLoader,
)


def pdf_loader(filepath: str, passwd=None) -> list[Document]:
    """PDF 加载：文字提取 → 不足时 OCR 扫描件"""
    # 1. 尝试 PyMuPDFLoader
    try:
        docs = PyMuPDFLoader(filepath).load()
        text = ''.join(d.page_content for d in docs)
        if len(text.strip()) > 50:
            return docs
    except Exception:
        pass

    # 2. 回退 PyPDFLoader
    docs = PyPDFLoader(filepath, passwd).load()
    text = ''.join(d.page_content for d in docs)
    if len(text.strip()) > 50:
        return docs

    # 3. 文字不足，OCR 扫描件 PDF
    try:
        import fitz
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        result_docs = []
        with fitz.open(filepath) as pdf:
            for page_num, page in enumerate(pdf):
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                ocr_result, _ = ocr(img_bytes)
                if ocr_result:
                    text = '\n'.join(line[1] for line in ocr_result if line[1])
                    result_docs.append(Document(
                        page_content=text,
                        metadata={"source": filepath, "page": page_num + 1}
                    ))
        if result_docs:
            logger.info(f"[OCR] 识别 PDF {filepath} 共 {len(result_docs)} 页")
            return result_docs
    except Exception as e:
        logger.warning(f"[OCR] PDF OCR 失败: {e}")

    # 4. 全部失败，返回空
    return []


def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8").load()


def csv_loader(filepath: str) -> list[Document]:
    return CSVLoader(filepath, encoding="utf-8").load()


def docx_loader(filepath: str) -> list[Document]:
    return Docx2txtLoader(filepath).load()


def xlsx_loader(filepath: str) -> list[Document]:
    return UnstructuredExcelLoader(filepath, mode="elements").load()


def get_file_documents(read_path: str) -> list[Document]:
    """根据文件后缀选择对应的加载器"""
    ext = os.path.splitext(read_path)[1].lower()
    if ext == ".txt":
        return txt_loader(read_path)
    if ext == ".pdf":
        return pdf_loader(read_path)
    if ext == ".csv":
        return csv_loader(read_path)
    if ext in (".doc", ".docx"):
        return docx_loader(read_path)
    if ext in (".xls", ".xlsx"):
        return xlsx_loader(read_path)
    logger.warning(f"[file_handler]不支持的文件类型: {ext}")
    return []
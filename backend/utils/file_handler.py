import os
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader, PyPDFLoader, CSVLoader, Docx2txtLoader, UnstructuredExcelLoader,
    PyMuPDFLoader,
)


def pdf_loader(filepath: str, passwd=None) -> list[Document]:
    """PDF 加载：文字提取 + 图片 OCR（图文混排也不漏）"""
    docs = []

    # 1. 文字提取
    try:
        docs = PyMuPDFLoader(filepath).load()
    except Exception:
        pass

    if not docs:
        try:
            docs = PyPDFLoader(filepath, passwd).load()
        except Exception:
            pass

    # 2. OCR 每页图片中的文字（图文混排也不漏）
    ocr_texts = _ocr_pdf_images(filepath)
    if ocr_texts:
        # 将 OCR 结果追加到对应页
        if docs:
            for i, ocr_text in enumerate(ocr_texts):
                if i < len(docs) and ocr_text.strip():
                    docs[i].page_content += "\n[图片文字] " + ocr_text
        else:
            # 纯扫描件，只有 OCR 结果
            for i, ocr_text in enumerate(ocr_texts):
                if ocr_text.strip():
                    docs.append(Document(
                        page_content=ocr_text,
                        metadata={"source": filepath, "page": i + 1}
                    ))

    if not docs:
        return []

    text = ''.join(d.page_content for d in docs)
    if len(text.strip()) > 20:
        return docs
    return []


def _ocr_pdf_images(filepath: str) -> list[str]:
    """对 PDF 每页做 OCR，返回每页识别文字列表"""
    try:
        import fitz
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        results = []
        with fitz.open(filepath) as pdf:
            for page in pdf:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                ocr_result, _ = ocr(img_bytes)
                if ocr_result:
                    text = '\n'.join(line[1] for line in ocr_result if line[1])
                    results.append(text)
                else:
                    results.append("")
        return results
    except Exception as e:
        logger.warning(f"[OCR] PDF 图片 OCR 失败: {e}")
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
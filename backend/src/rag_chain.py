"""
Luồng RAG (Retrieval-Augmented Generation).

Module này chịu trách nhiệm:
    1. Kết nối tới ChromaDB đã được tạo bởi embed_data.py.
    2. Truy xuất (retrieve) các đoạn văn bản liên quan tới câu hỏi.
    3. Đưa ngữ cảnh + câu hỏi vào Prompt và gọi Gemini để sinh câu trả lời.

Thiết kế lazy-init singleton: chain chỉ được khởi tạo MỘT lần ở lần gọi đầu
tiên rồi tái sử dụng, tránh nạp lại model/vector store cho mỗi request.
"""

import os
import sys

# Ép stdout/stderr sang UTF-8 để in được tiếng Việt trên Windows console (cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Cấu hình.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

EMBEDDING_MODEL = "models/gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"  # Có thể đổi sang "gemini-2.5-pro" nếu cần chất lượng cao hơn.
COLLECTION_NAME = "lich_su_11"
RETRIEVER_K = 4  # Số đoạn ngữ cảnh lấy ra cho mỗi câu hỏi.

# Prompt đúng theo yêu cầu: ràng buộc model chỉ trả lời dựa trên bối cảnh.
PROMPT_TEMPLATE = (
    "Bạn là gia sư Sử lớp 11. Trả lời chính xác, có trích dẫn từ bối cảnh. "
    "Không biết thì nói không biết, tuyệt đối không bịa đặt. \n"
    "Bối cảnh: {context} \n"
    "Câu hỏi: {question}"
)

# Singleton nội bộ - giữ chain và retriever sau lần khởi tạo đầu tiên.
_rag_chain = None
_retriever = None


def _format_docs(docs: list[Document]) -> str:
    """Gộp nội dung các Document truy xuất được thành một khối ngữ cảnh.

    Args:
        docs: Danh sách Document từ retriever.

    Returns:
        Chuỗi ngữ cảnh, các đoạn cách nhau bằng dòng trống.
    """
    return "\n\n".join(doc.page_content for doc in docs)


def _build_chain():
    """Khởi tạo retriever + chain RAG (chỉ gọi một lần).

    Raises:
        RuntimeError: Khi thiếu GOOGLE_API_KEY hoặc chưa có chroma_db.
    """
    global _rag_chain, _retriever

    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "Thiếu biến môi trường GOOGLE_API_KEY. Hãy cấu hình trong file .env."
        )

    if not os.path.isdir(CHROMA_DIR) or not os.listdir(CHROMA_DIR):
        raise RuntimeError(
            f"Chưa có vector store tại {CHROMA_DIR}. "
            "Hãy chạy 'python src/clean_data.py' và 'python src/embed_data.py' trước."
        )

    print("[rag_chain] Khởi tạo embeddings & vector store...")
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    vector_store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )
    _retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVER_K})

    print(f"[rag_chain] Khởi tạo LLM: {CHAT_MODEL}")
    llm = ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        temperature=0.3,  # Thấp để câu trả lời bám sát ngữ cảnh, ít "bịa".
    )

    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)

    # Xây dựng chain theo cú pháp LCEL:
    #   context (từ retriever) + question -> prompt -> llm -> parse text.
    _rag_chain = (
        {
            "context": _retriever | _format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    print("[rag_chain] ✅ RAG chain sẵn sàng.")


def get_rag_chain():
    """Trả về RAG chain (khởi tạo lần đầu nếu cần)."""
    if _rag_chain is None:
        _build_chain()
    return _rag_chain


def answer_question(question: str) -> dict:
    """Trả lời một câu hỏi của người dùng qua luồng RAG.

    Args:
        question: Câu hỏi (đã được validate ở tầng API).

    Returns:
        dict gồm:
            - answer: Câu trả lời do Gemini sinh ra.
            - sources: Danh sách trích đoạn ngữ cảnh được dùng (để minh bạch).

    Raises:
        RuntimeError: Khi cấu hình thiếu (API key / vector store).
        ValueError: Khi câu hỏi rỗng.
    """
    if not question or not question.strip():
        raise ValueError("Câu hỏi không được để trống.")

    chain = get_rag_chain()
    question = question.strip()

    # Lấy câu trả lời.
    answer = chain.invoke(question)

    # Lấy thêm các đoạn nguồn để hiển thị (giúp người học kiểm chứng).
    source_docs = _retriever.invoke(question) if _retriever else []
    sources = [doc.page_content for doc in source_docs]

    return {"answer": answer, "sources": sources}

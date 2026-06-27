"""
Luồng RAG (Retrieval-Augmented Generation).

Module này chịu trách nhiệm:
    1. Kết nối tới ChromaDB đã được tạo bởi embed_data.py.
    2. Truy xuất (retrieve) các đoạn văn bản liên quan tới câu hỏi.
    3. Đưa ngữ cảnh + câu hỏi vào Prompt và gọi Gemini để sinh câu trả lời.

Thiết kế:
    - Lazy-init singleton cho retriever/prompt: chỉ nạp MỘT lần rồi tái sử dụng.
    - XOAY VÒNG MODEL CHAT: mỗi model Gemini có quota free tier riêng theo ngày;
      khi một model hết quota (429) sẽ tự chuyển sang model kế tiếp -> bền hơn.
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
from langchain_core.prompts import PromptTemplate
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

# Danh sách model chat để XOAY VÒNG khi gặp 429 (hết quota ngày).
# Đặt model còn nhiều quota lên đầu. Có thể chỉnh qua env CHAT_MODELS
# (các model ngăn cách bởi dấu phẩy).
CHAT_MODELS = [
    m.strip()
    for m in os.getenv(
        "CHAT_MODELS",
        "gemini-flash-latest,gemini-2.5-flash,gemini-2.0-flash,gemini-2.5-flash-lite",
    ).split(",")
    if m.strip()
]

COLLECTION_NAME = "lich_su_11"
RETRIEVER_K = 4  # Số đoạn ngữ cảnh lấy ra cho mỗi câu hỏi.

# Prompt đúng theo yêu cầu: ràng buộc model chỉ trả lời dựa trên bối cảnh.
PROMPT_TEMPLATE = (
    "Bạn là gia sư Sử lớp 11. Trả lời chính xác, có trích dẫn từ bối cảnh. "
    "Không biết thì nói không biết, tuyệt đối không bịa đặt. \n"
    "Bối cảnh: {context} \n"
    "Câu hỏi: {question}"
)

# Singleton nội bộ.
_retriever = None
_prompt: PromptTemplate | None = None
_llm_cache: dict[str, ChatGoogleGenerativeAI] = {}  # model_name -> instance


class QuotaExhaustedError(RuntimeError):
    """Ném ra khi TẤT CẢ model chat đều hết quota (429)."""


def _is_quota_error(err: Exception) -> bool:
    """Nhận diện lỗi hết quota (429 RESOURCE_EXHAUSTED)."""
    text = str(err)
    return "RESOURCE_EXHAUSTED" in text or "429" in text


def _format_docs(docs: list[Document]) -> str:
    """Gộp nội dung các Document truy xuất được thành một khối ngữ cảnh."""
    return "\n\n".join(doc.page_content for doc in docs)


def _init_resources() -> None:
    """Khởi tạo retriever + prompt (chỉ gọi một lần).

    Raises:
        RuntimeError: Khi thiếu GOOGLE_API_KEY hoặc chưa có chroma_db.
    """
    global _retriever, _prompt

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
    _prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    print(f"[rag_chain] ✅ Sẵn sàng. Model chat (xoay vòng): {CHAT_MODELS}")


def _get_llm(model: str) -> ChatGoogleGenerativeAI:
    """Lấy (hoặc tạo & cache) một LLM theo tên model."""
    if model not in _llm_cache:
        _llm_cache[model] = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.3,  # Thấp để bám sát ngữ cảnh, hạn chế "bịa".
        )
    return _llm_cache[model]


def _generate_answer(context: str, question: str) -> str:
    """Sinh câu trả lời, tự xoay vòng qua các model khi gặp 429.

    Args:
        context: Khối ngữ cảnh đã gộp từ các đoạn truy xuất.
        question: Câu hỏi của người dùng.

    Returns:
        Câu trả lời (text).

    Raises:
        QuotaExhaustedError: Khi mọi model đều hết quota.
    """
    prompt_value = _prompt.format(context=context, question=question)

    last_error: Exception | None = None
    for model in CHAT_MODELS:
        try:
            response = _get_llm(model).invoke(prompt_value)
            print(f"[rag_chain] Trả lời bằng model: {model}")
            # response.content có thể là str hoặc list parts -> chuẩn hoá về str.
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    part if isinstance(part, str) else part.get("text", "")
                    for part in content
                )
            return content
        except Exception as err:  # noqa: BLE001
            last_error = err
            if _is_quota_error(err):
                print(f"[rag_chain] Model '{model}' hết quota (429) -> thử model kế.",
                      file=sys.stderr)
                continue
            # Lỗi khác (key sai, mạng...) -> ném ngay để tầng trên xử lý.
            raise

    # Hết tất cả model mà vẫn 429.
    raise QuotaExhaustedError(
        "Tất cả model chat đều đã hết quota hôm nay. Vui lòng thử lại sau."
    ) from last_error


def answer_question(question: str) -> dict:
    """Trả lời một câu hỏi của người dùng qua luồng RAG.

    Args:
        question: Câu hỏi (đã được validate ở tầng API).

    Returns:
        dict gồm:
            - answer: Câu trả lời do Gemini sinh ra.
            - sources: Danh sách trích đoạn ngữ cảnh được dùng (để minh bạch).

    Raises:
        ValueError: Khi câu hỏi rỗng.
        RuntimeError / QuotaExhaustedError: Khi cấu hình thiếu hoặc hết quota.
    """
    if not question or not question.strip():
        raise ValueError("Câu hỏi không được để trống.")

    if _retriever is None or _prompt is None:
        _init_resources()

    question = question.strip()

    # 1) Truy xuất ngữ cảnh liên quan.
    source_docs = _retriever.invoke(question)
    context = _format_docs(source_docs)

    # 2) Sinh câu trả lời (có xoay vòng model).
    answer = _generate_answer(context, question)

    # 3) Trả kèm các đoạn nguồn để người học kiểm chứng.
    sources = [doc.page_content for doc in source_docs]
    return {"answer": answer, "sources": sources}

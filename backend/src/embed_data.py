"""
Script 2: Chunking & Embedding.

Quy trình:
    1. Đọc file su_11_cleaned.txt (kết quả của clean_data.py).
    2. Cắt văn bản thành các đoạn nhỏ (chunk) bằng RecursiveCharacterTextSplitter
       với chunk_size=1000, chunk_overlap=200.
    3. Nhúng (embedding) từng chunk bằng GoogleGenerativeAIEmbeddings
       (model="models/embedding-001").
    4. Lưu vector vào ChromaDB (persistent) tại backend/chroma_db.

Cách chạy:
    python src/embed_data.py

Yêu cầu: biến môi trường GOOGLE_API_KEY phải được thiết lập.
"""

import os
import sys

# Ép stdout/stderr sang UTF-8 để in được tiếng Việt trên Windows console (cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Nạp biến môi trường từ file .env (nếu có) ngay khi import module.
load_dotenv()

# ---------------------------------------------------------------------------
# Cấu hình đường dẫn & tham số.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
CLEANED_TXT_PATH = os.path.join(BASE_DIR, "su_11_cleaned.txt")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "models/gemini-embedding-001"
COLLECTION_NAME = "lich_su_11"


def load_cleaned_text(path: str) -> str:
    """Đọc nội dung file text đã làm sạch.

    Args:
        path: Đường dẫn tới file su_11_cleaned.txt.

    Returns:
        Nội dung text.

    Raises:
        FileNotFoundError: Khi chưa chạy clean_data.py để sinh file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy {path}. Hãy chạy 'python src/clean_data.py' trước."
        )

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_into_chunks(text: str) -> list:
    """Cắt văn bản dài thành các chunk nhỏ có chồng lấp (overlap).

    Chồng lấp giúp giữ ngữ cảnh xuyên suốt giữa các chunk liền kề, tăng chất
    lượng truy xuất khi RAG.

    Args:
        text: Văn bản đầu vào.

    Returns:
        Danh sách Document đã được cắt.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Ưu tiên cắt theo đoạn -> câu -> từ để giữ ngữ nghĩa tự nhiên.
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    documents = splitter.create_documents([text])
    print(f"[embed_data] Đã cắt thành {len(documents)} chunk "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return documents


def build_vector_store(documents: list) -> None:
    """Nhúng các chunk và lưu vào ChromaDB (persistent).

    Args:
        documents: Danh sách Document cần embedding.

    Raises:
        RuntimeError: Khi thiếu GOOGLE_API_KEY hoặc embedding thất bại.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "Thiếu biến môi trường GOOGLE_API_KEY. "
            "Hãy tạo file .env từ .env.example và điền API key."
        )

    print(f"[embed_data] Khởi tạo embeddings model: {EMBEDDING_MODEL}")
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

    print(f"[embed_data] Đang nhúng {len(documents)} chunk và lưu vào: {CHROMA_DIR}")
    print("[embed_data] (Bước này gọi Google API, có thể mất vài phút...)")

    # Chroma.from_documents sẽ tự động gọi embeddings cho toàn bộ documents và
    # ghi xuống đĩa tại persist_directory.
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME,
    )

    print(f"[embed_data] ✅ Hoàn tất. Vector store đã lưu tại: {CHROMA_DIR}")


def main() -> None:
    """Điểm vào của script: đọc text -> chunk -> embedding -> lưu Chroma."""
    try:
        text = load_cleaned_text(CLEANED_TXT_PATH)
        documents = split_into_chunks(text)
        if not documents:
            raise RuntimeError("Không có chunk nào được tạo (file rỗng?).")
        build_vector_store(documents)
    except (FileNotFoundError, RuntimeError) as err:
        print(f"[embed_data] ❌ {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # noqa: BLE001 - log rõ ràng mọi lỗi còn lại.
        print(f"[embed_data] ❌ Lỗi không mong muốn: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

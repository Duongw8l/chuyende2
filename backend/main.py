"""
API Backend bằng FastAPI cho Chatbot RAG Lịch sử 11.

Tính năng:
    - CORS middleware: cho phép frontend (khác origin) gọi API.
    - Rate limiting: giới hạn số request/phút để chống lạm dụng (slowapi).
    - Validate input bằng Pydantic.
    - Endpoint POST /chat: nhận câu hỏi -> luồng RAG -> trả câu trả lời.
    - Endpoint GET /health: kiểm tra trạng thái service.

Chạy local:
    uvicorn main:app --reload --port 8000
"""

import os
import sys

# Ép stdout/stderr sang UTF-8 để in được log tiếng Việt trên Windows console (cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.rag_chain import answer_question

load_dotenv()

# ---------------------------------------------------------------------------
# Cấu hình ứng dụng.
# ---------------------------------------------------------------------------
# Danh sách origin được phép, đọc từ env (ngăn cách bởi dấu phẩy).
# Mặc định cho phép localhost dev của Next.js.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

# Giới hạn rate mặc định cho mỗi IP (có thể chỉnh qua env).
RATE_LIMIT = os.getenv("RATE_LIMIT", "20/minute")

# Khởi tạo limiter dựa trên địa chỉ IP của client.
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Chatbot RAG Lịch sử 11",
    description="API trả lời câu hỏi môn Lịch sử lớp 11 dựa trên SGK (RAG + Gemini).",
    version="1.0.0",
)

# Gắn limiter vào app và đăng ký handler cho lỗi vượt giới hạn.
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Trả lỗi 429 thân thiện khi client gửi quá nhiều request."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Bạn gửi quá nhiều yêu cầu. Vui lòng thử lại sau ít phút."},
    )


# Cấu hình CORS để frontend gọi được API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models - validate dữ liệu vào/ra.
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """Schema cho body của request /chat."""

    # min_length=1 đảm bảo không nhận câu hỏi rỗng; max_length chống spam.
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Câu hỏi của người dùng về môn Lịch sử 11.",
    )


class ChatResponse(BaseModel):
    """Schema cho response trả về client."""

    answer: str
    sources: list[str] = []


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    """Health check đơn giản cho Railway / load balancer."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    """Nhận câu hỏi, đưa qua luồng RAG và trả về câu trả lời.

    Lưu ý: tham số `request` là bắt buộc để slowapi đọc được IP client.

    Args:
        request: Request gốc (slowapi sử dụng).
        payload: Body đã validate gồm `question`.

    Returns:
        ChatResponse gồm câu trả lời và các đoạn nguồn.
    """
    try:
        result = answer_question(payload.question)
        return ChatResponse(answer=result["answer"], sources=result["sources"])
    except ValueError as err:
        # Lỗi do dữ liệu đầu vào -> 400 Bad Request.
        return JSONResponse(status_code=400, content={"detail": str(err)})
    except RuntimeError as err:
        # Lỗi cấu hình (thiếu API key / chưa embed) -> 503 Service Unavailable.
        return JSONResponse(status_code=503, content={"detail": str(err)})
    except Exception as err:  # noqa: BLE001 - bắt mọi lỗi còn lại để không lộ stacktrace.
        print(f"[main] ❌ Lỗi khi xử lý /chat: {err}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Đã có lỗi xảy ra phía máy chủ. Vui lòng thử lại."},
        )

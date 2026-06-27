# 📚 Chatbot RAG — Gia sư Lịch sử lớp 11

Chatbot hỏi đáp môn **Lịch sử lớp 11** (bộ SGK *Kết nối tri thức với cuộc sống*) sử dụng kiến trúc
**RAG (Retrieval-Augmented Generation)**. Toàn bộ luồng AI dùng **Google Gemini** thông qua **LangChain**.

Dự án theo kiến trúc **Decoupled / Monorepo**:

| Service    | Công nghệ                                   | Vai trò                                      |
| ---------- | ------------------------------------------- | -------------------------------------------- |
| `backend`  | Python, FastAPI, LangChain, ChromaDB, Gemini | API + xử lý dữ liệu + luồng RAG              |
| `frontend` | Node.js, Next.js (App Router), Tailwind CSS  | Giao diện chat giống ChatGPT                  |

---

## 🗂️ Cấu trúc thư mục

```
.
├── backend/
│   ├── data/                  # Đặt file "SGK Lịch sử 11_KNTT (1).pdf" vào đây
│   ├── src/
│   │   ├── clean_data.py      # B1: PDF -> làm sạch -> su_11_cleaned.txt
│   │   ├── embed_data.py      # B2: chunk + embedding -> chroma_db
│   │   └── rag_chain.py       # Luồng RAG (retrieve + prompt + Gemini)
│   ├── main.py                # FastAPI (CORS, rate limit, /chat)
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── railway.json
├── frontend/
│   ├── app/                   # Next.js App Router (layout, page, css)
│   ├── components/            # ChatWindow, MessageBubble, ChatInput
│   ├── lib/api.ts             # Gọi backend API
│   ├── package.json
│   ├── Dockerfile
│   └── railway.json
└── README.md
```

---

## 🔑 Chuẩn bị

1. **Google API Key**: tạo tại <https://aistudio.google.com/app/apikey>.
2. **File PDF**: đặt `SGK Lịch sử 11_KNTT (1).pdf` vào thư mục `backend/data/`.

---

## 💻 Chạy Local

### 1. Backend

```bash
cd backend

# Tạo & kích hoạt virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Cài thư viện
pip install -r requirements.txt

# Tạo file .env và điền GOOGLE_API_KEY
cp .env.example .env      # Windows: copy .env.example .env

# B1: Làm sạch dữ liệu từ PDF -> su_11_cleaned.txt
python src/clean_data.py

# B2: Chunk + embedding -> chroma_db (gọi Google API, mất vài phút)
python src/embed_data.py

# Khởi động API
uvicorn main:app --reload --port 8000
```

Kiểm tra nhanh:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"Cách mạng tư sản là gì?\"}"
```

> 💡 Tài liệu API tự sinh tại <http://localhost:8000/docs>.

### 2. Frontend

```bash
cd frontend

# Cài dependency
npm install

# Tạo .env.local và trỏ tới backend
cp .env.example .env.local   # Windows: copy .env.example .env.local
# Nội dung: NEXT_PUBLIC_API_URL=http://localhost:8000

# Chạy dev server
npm run dev
```

Mở <http://localhost:3000> để trò chuyện với gia sư.

---

## 🚀 Deploy lên Railway

Mỗi thư mục (`backend`, `frontend`) là **một service riêng**, đều có `Dockerfile` và `railway.json`.

### Bước 1 — Tạo Project & 2 service

1. Tạo Project mới trên [Railway](https://railway.app), kết nối repo GitHub này.
2. Tạo **2 service** từ cùng repo, mỗi service trỏ **Root Directory** lần lượt là `backend` và `frontend`.
   Railway sẽ tự nhận `Dockerfile` trong từng thư mục.

### Bước 2 — Cấu hình biến môi trường

**Service `backend`:**

| Biến              | Giá trị                                              |
| ----------------- | ---------------------------------------------------- |
| `GOOGLE_API_KEY`  | API key Gemini của bạn                               |
| `ALLOWED_ORIGINS` | URL frontend, ví dụ `https://your-frontend.up.railway.app` |
| `RATE_LIMIT`      | `20/minute` (tuỳ chọn)                               |

**Service `frontend`:**

| Biến                  | Giá trị                                       |
| --------------------- | --------------------------------------------- |
| `NEXT_PUBLIC_API_URL` | URL backend, ví dụ `https://your-backend.up.railway.app` |

> ⚠️ `NEXT_PUBLIC_API_URL` được nhúng lúc **build**. Sau khi đổi giá trị, hãy **redeploy** frontend.

### Bước 3 — Dữ liệu RAG (quan trọng)

**Chiến lược mặc định (khuyến nghị): commit sẵn vector store.**
Thư mục `backend/chroma_db/` (đã build sẵn) **được commit vào repo**, nên khi deploy container chỉ việc
phục vụ — `entrypoint.sh` thấy `chroma_db` không rỗng sẽ **bỏ qua bước OCR/embedding**. Nhờ đó:

- Khởi động nhanh, không gọi API lúc boot, không phụ thuộc quota.
- **Không cần** commit file PDF 19 MB.
- ⚠️ **Không** mount Railway Volume vào `/app/chroma_db` (volume rỗng sẽ che mất DB đã commit).

**Khi muốn build lại dữ liệu (vd: OCR thêm trang):**
Chạy local `python src/clean_data.py` + `python src/embed_data.py`, rồi commit `chroma_db/` mới.

**Phương án thay thế — build tại runtime:** xoá `chroma_db/` khỏi repo và đặt PDF vào `backend/data/`.
Khi đó `entrypoint.sh` sẽ tự OCR + embed ở lần khởi động đầu (cần `GOOGLE_API_KEY` + quota, chậm hơn).
Nên kết hợp **Railway Volume** mount `/app/chroma_db` để chỉ build một lần.

### Bước 4 — Healthcheck

Backend expose `GET /health` (đã khai báo trong `railway.json`) để Railway xác định service sẵn sàng.

---

## 🧩 Luồng hoạt động (RAG)

```
PDF ──clean_data──► su_11_cleaned.txt ──embed_data──► ChromaDB (vector)
                                                          │
Người dùng hỏi ─► Frontend ─► POST /chat ─► retrieve (top-k) ─► Prompt + Gemini ─► Trả lời + nguồn
```

**Prompt hệ thống:**

> *Bạn là gia sư Sử lớp 11. Trả lời chính xác, có trích dẫn từ bối cảnh. Không biết thì nói không biết,
> tuyệt đối không bịa đặt.*

---

## 🛠️ Công nghệ chính

- **Backend**: FastAPI, Uvicorn, Pydantic, SlowAPI (rate limit), PyMuPDF, LangChain,
  `langchain-google-genai`, ChromaDB.
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS.
- **AI**: Gemini `gemini-embedding-001` (embedding) + `gemini-2.5-flash` (chat).

---

## ❓ Xử lý sự cố

| Triệu chứng                                   | Nguyên nhân & cách khắc phục                                            |
| --------------------------------------------- | ---------------------------------------------------------------------- |
| `Thiếu biến môi trường GOOGLE_API_KEY`        | Chưa tạo `.env` hoặc chưa điền key.                                     |
| `Chưa có vector store tại .../chroma_db`      | Chưa chạy `embed_data.py` (hoặc volume trống).                          |
| Frontend báo *Không kết nối được tới máy chủ* | Backend chưa chạy, sai `NEXT_PUBLIC_API_URL`, hoặc CORS chặn origin.    |
| Lỗi 429                                        | Vượt rate limit — chờ một lát hoặc tăng `RATE_LIMIT`.                   |
```

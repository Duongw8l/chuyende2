# =====================================================================
# Dockerfile cho BACKEND (FastAPI + RAG + Gemini).
# =====================================================================
FROM python:3.11-slim

# Biến môi trường tối ưu cho Python trong container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài các gói hệ thống cần thiết (build tools cho một số dependency của chromadb).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Cài dependency trước (tận dụng cache layer khi code thay đổi).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy toàn bộ source (bao gồm data/ chứa PDF nếu có).
COPY . .

# Cấp quyền thực thi cho entrypoint.
RUN chmod +x entrypoint.sh

# Railway sẽ map cổng qua biến PORT; expose 8000 cho local.
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

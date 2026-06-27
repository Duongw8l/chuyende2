#!/usr/bin/env bash
# =====================================================================
# Entrypoint cho backend container.
# - Nếu chưa có vector store (chroma_db rỗng) thì tự động chạy pipeline:
#     clean_data.py -> embed_data.py
#   để xây dựng dữ liệu từ PDF trong thư mục data/.
# - Sau đó khởi động API bằng uvicorn.
#
# Lưu ý: bước embedding cần GOOGLE_API_KEY và file PDF trong data/.
# =====================================================================
set -e

CHROMA_DIR="/app/chroma_db"

# Kiểm tra chroma_db tồn tại và có dữ liệu hay chưa.
if [ -d "$CHROMA_DIR" ] && [ "$(ls -A "$CHROMA_DIR" 2>/dev/null)" ]; then
  echo "[entrypoint] Đã có vector store sẵn, bỏ qua bước embedding."
else
  echo "[entrypoint] Chưa có vector store -> bắt đầu xây dựng dữ liệu RAG..."
  python src/clean_data.py
  python src/embed_data.py
fi

# Railway cung cấp biến PORT động; mặc định 8000 khi chạy local.
echo "[entrypoint] Khởi động API trên cổng ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"

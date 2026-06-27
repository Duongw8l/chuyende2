"""
Script 1: Đọc PDF SGK Lịch sử 11 và làm sạch dữ liệu.

Hỗ trợ 2 loại PDF:
    1. PDF có text layer  -> trích trực tiếp bằng PyMuPDF (fitz).
    2. PDF scan (ảnh)     -> tự động fallback sang OCR bằng Gemini (multimodal).
       (Phù hợp yêu cầu: toàn bộ luồng AI dùng hệ sinh thái Google.)

Sau khi có text thô, dùng Regular Expression để làm sạch:
    - Bỏ các dòng chỉ chứa chữ số (số trang / lỗi OCR).
    - Bỏ các dòng bắt đầu bằng chữ "Hình" (chú thích hình ảnh).
    - Xoá cụm từ thừa "KẾT NỐI TRI THỨC VỚI CUỘC SỐNG".
    - Nối các câu bị ngắt dòng giữa chừng.
Kết quả lưu ra file su_11_cleaned.txt.

Cách chạy:
    python src/clean_data.py
"""

import os
import re
import sys
import time

import fitz  # PyMuPDF

# Ép stdout/stderr sang UTF-8 để in được tiếng Việt trên Windows console (cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Cấu hình đường dẫn (tính tương đối so với thư mục backend/).
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
DATA_DIR = os.path.join(BASE_DIR, "data")
PDF_FILENAME = "SGK Lịch sử 11_KNTT (1).pdf"
PDF_PATH = os.path.join(DATA_DIR, PDF_FILENAME)
OUTPUT_PATH = os.path.join(BASE_DIR, "su_11_cleaned.txt")

# Cụm từ thừa lặp lại ở chân/đầu trang cần loại bỏ.
REDUNDANT_PHRASE = "KẾT NỐI TRI THỨC VỚI CUỘC SỐNG"

# Các ký tự được coi là "kết thúc câu". Nếu một dòng KHÔNG kết thúc bằng các ký
# tự này thì coi như câu bị ngắt dòng giữa chừng và cần nối với dòng kế tiếp.
SENTENCE_ENDINGS = (".", "!", "?", ":", ";", "…", '"', "”", ")")

# ---------------------------------------------------------------------------
# Cấu hình OCR bằng Gemini.
# ---------------------------------------------------------------------------
# Danh sách model OCR (multimodal) để XOAY VÒNG: mỗi model có quota free tier
# riêng theo ngày, nên khi một model hết quota (429) sẽ tự chuyển sang model kế.
OCR_MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
]
OCR_DPI = 200  # Độ phân giải khi render trang PDF -> ảnh (cao hơn = nét hơn).
# Chờ giữa các lần gọi. Paid tier rate limit cao nên để nhỏ; chỉnh qua env nếu cần.
OCR_DELAY_SECONDS = float(os.getenv("OCR_DELAY_SECONDS", "1"))
OCR_MAX_RETRIES = 3  # Số lần thử lại cho lỗi TẠM THỜI (503/timeout) trên 1 model.

# Thư mục cache: lưu kết quả OCR từng trang ngay sau khi thành công.
# Nhờ đó nếu bị ngắt giữa chừng, lần chạy sau sẽ BỎ QUA các trang đã xong
# (resumable) -> không tốn lại quota.
OCR_CACHE_DIR = os.path.join(BASE_DIR, ".ocr_cache")

# Giới hạn số trang OCR mỗi lần chạy (0 = không giới hạn). Hữu ích khi free tier
# có quota thấp: chạy nhiều phiên, mỗi phiên vài trang. Đọc từ env MAX_OCR_PAGES.
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", "0"))

OCR_PROMPT = (
    "Đây là ảnh chụp một trang sách giáo khoa Lịch sử lớp 11 bằng tiếng Việt. "
    "Hãy trích xuất TOÀN BỘ phần văn bản (chữ) trong ảnh, giữ nguyên nội dung và "
    "thứ tự đọc tự nhiên. Bỏ qua hình ảnh minh hoạ. Chỉ trả về phần văn bản, "
    "KHÔNG thêm lời giải thích, KHÔNG thêm tiêu đề của bạn."
)

# Tập các model đã xác định hết quota ngày -> bỏ qua trong phiên hiện tại.
_exhausted_models: set[str] = set()


def extract_text_native(doc: "fitz.Document") -> str:
    """Trích text trực tiếp từ PDF có text layer.

    Args:
        doc: Tài liệu PDF đã mở.

    Returns:
        Text gộp từ tất cả các trang (có thể rỗng nếu PDF là ảnh scan).
    """
    parts = [page.get_text("text") for page in doc]
    return "\n".join(parts)


def _is_quota_error(err: Exception) -> bool:
    """Nhận diện lỗi hết quota theo ngày (429 RESOURCE_EXHAUSTED)."""
    text = str(err)
    return "RESOURCE_EXHAUSTED" in text or "429" in text


def _cache_path(page_no: int) -> str:
    """Đường dẫn file cache cho một trang."""
    return os.path.join(OCR_CACHE_DIR, f"page_{page_no:03d}.txt")


def _ocr_page_with_gemini(client, img_bytes: bytes, page_no: int, total: int) -> str | None:
    """OCR một trang bằng Gemini, tự xoay vòng qua các model khi hết quota.

    Args:
        client: google.genai.Client đã khởi tạo.
        img_bytes: Ảnh PNG của trang.
        page_no: Số thứ tự trang (để log).
        total: Tổng số trang (để log).

    Returns:
        - Chuỗi text nếu OCR thành công (có thể rỗng nếu trang không có chữ).
        - None nếu TẤT CẢ model đều hết quota (báo hiệu nên dừng phiên).
    """
    from google.genai import types

    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")

    for model in OCR_MODELS:
        if model in _exhausted_models:
            continue  # Bỏ qua model đã biết hết quota.

        for attempt in range(1, OCR_MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[image_part, OCR_PROMPT],
                )
                text = (response.text or "").strip()
                print(f"[clean_data][OCR] Trang {page_no}/{total} ({model}): "
                      f"{len(text)} ký tự")
                return text
            except Exception as err:  # noqa: BLE001
                if _is_quota_error(err):
                    # Hết quota ngày cho model này -> đánh dấu và chuyển model khác ngay.
                    print(f"[clean_data][OCR] Model '{model}' hết quota ngày -> chuyển model.",
                          file=sys.stderr)
                    _exhausted_models.add(model)
                    break
                # Lỗi tạm thời (503/timeout...) -> thử lại với backoff.
                wait = OCR_DELAY_SECONDS * attempt
                print(f"[clean_data][OCR] Trang {page_no} ({model}) lỗi tạm thời "
                      f"(lần {attempt}/{OCR_MAX_RETRIES}): {err}. Chờ {wait}s...",
                      file=sys.stderr)
                time.sleep(wait)

    # Không model nào xử lý được trang này.
    return None


def extract_text_with_ocr(doc: "fitz.Document") -> str:
    """OCR PDF scan bằng Gemini, có cache từng trang (resumable) và xoay vòng model.

    Args:
        doc: Tài liệu PDF đã mở.

    Returns:
        Text gộp từ tất cả các trang (lấy từ cache, kể cả các phiên trước).

    Raises:
        RuntimeError: Khi thiếu GOOGLE_API_KEY hoặc SDK chưa cài.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "PDF là bản scan -> cần OCR bằng Gemini, nhưng thiếu GOOGLE_API_KEY. "
            "Hãy cấu hình API key trong file .env."
        )

    try:
        from google import genai
    except ImportError as err:  # pragma: no cover
        raise RuntimeError(
            "Thiếu thư viện google-genai. Hãy chạy: pip install -r requirements.txt"
        ) from err

    os.makedirs(OCR_CACHE_DIR, exist_ok=True)
    client = genai.Client(api_key=api_key)
    total = doc.page_count
    print(f"[clean_data] PDF là bản scan -> OCR {total} trang (cache tại {OCR_CACHE_DIR}).")
    if MAX_OCR_PAGES:
        print(f"[clean_data] Giới hạn phiên này: tối đa {MAX_OCR_PAGES} trang OCR mới.")

    ocr_done_this_run = 0  # Đếm số trang GỌI API thật trong phiên (để áp MAX_OCR_PAGES).

    for index, page in enumerate(doc, start=1):
        cache_file = _cache_path(index)

        # 1) Nếu đã có cache -> bỏ qua, không tốn quota.
        if os.path.exists(cache_file):
            continue

        # 2) Nếu đã đạt giới hạn trang/phiên -> dừng OCR thêm.
        if MAX_OCR_PAGES and ocr_done_this_run >= MAX_OCR_PAGES:
            print(f"[clean_data] Đã đạt giới hạn {MAX_OCR_PAGES} trang/phiên -> dừng.")
            break

        # 3) Render trang -> ảnh -> OCR.
        pix = page.get_pixmap(dpi=OCR_DPI)
        text = _ocr_page_with_gemini(client, pix.tobytes("png"), index, total)

        if text is None:
            # Tất cả model đều hết quota -> dừng phiên, giữ nguyên cache đã có.
            print("[clean_data] ⚠️ Tất cả model đã hết quota hôm nay. Dừng phiên OCR.",
                  file=sys.stderr)
            print("[clean_data] Chạy lại script sau (quota reset) để OCR tiếp các trang còn lại.",
                  file=sys.stderr)
            break

        # 4) Ghi cache NGAY (kể cả rỗng) để lần sau không OCR lại trang này.
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(text)
        ocr_done_this_run += 1

        if index < total:
            time.sleep(OCR_DELAY_SECONDS)

    return _assemble_from_cache(total)


def _assemble_from_cache(total_pages: int) -> str:
    """Gộp text của các trang đã OCR từ thư mục cache theo đúng thứ tự.

    Args:
        total_pages: Tổng số trang của PDF.

    Returns:
        Text gộp; báo log số trang đã có / còn thiếu.
    """
    parts: list[str] = []
    cached = 0
    for index in range(1, total_pages + 1):
        cache_file = _cache_path(index)
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                parts.append(f.read())
            cached += 1

    missing = total_pages - cached
    print(f"[clean_data] Đã gộp {cached}/{total_pages} trang từ cache "
          f"({missing} trang chưa OCR).")
    return "\n".join(parts)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Trích text từ PDF, tự chọn native hoặc OCR tuỳ loại PDF.

    Args:
        pdf_path: Đường dẫn tuyệt đối tới file PDF.

    Returns:
        Text thô của toàn bộ tài liệu.

    Raises:
        FileNotFoundError: Khi không tìm thấy file PDF.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"Không tìm thấy file PDF tại: {pdf_path}. "
            f"Hãy đặt file '{PDF_FILENAME}' vào thư mục backend/data/."
        )

    print(f"[clean_data] Đang mở PDF: {pdf_path}")
    with fitz.open(pdf_path) as doc:
        print(f"[clean_data] Tổng số trang: {doc.page_count}")

        native_text = extract_text_native(doc)
        # Nếu lượng text quá ít (< 100 ký tự) -> coi như PDF scan, chuyển sang OCR.
        if len(native_text.strip()) >= 100:
            print("[clean_data] PDF có text layer -> trích trực tiếp.")
            return native_text

        return extract_text_with_ocr(doc)


def clean_text(raw_text: str) -> str:
    """Làm sạch text thô bằng các luật Regex.

    Args:
        raw_text: Text thô trích từ PDF.

    Returns:
        Text đã được làm sạch và nối câu hoàn chỉnh.
    """
    # 1) Xoá cụm từ thừa ở mọi vị trí.
    text = re.sub(re.escape(REDUNDANT_PHRASE), " ", raw_text)

    # Compile sẵn các pattern để tái dùng trong vòng lặp -> hiệu năng tốt hơn.
    only_digits_pattern = re.compile(r"^\s*\d+\s*$")  # dòng chỉ có chữ số
    figure_caption_pattern = re.compile(r"^\s*Hình", re.IGNORECASE)  # dòng "Hình ..."
    multi_space_pattern = re.compile(r"[ \t]+")  # gộp khoảng trắng dư

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            continue
        # 2) Bỏ dòng chỉ chứa chữ số (số trang / lỗi OCR).
        if only_digits_pattern.match(stripped):
            continue
        # 3) Bỏ dòng chú thích bắt đầu bằng "Hình".
        if figure_caption_pattern.match(stripped):
            continue

        stripped = multi_space_pattern.sub(" ", stripped)
        cleaned_lines.append(stripped)

    # 4) Nối các câu bị ngắt dòng giữa chừng.
    return _join_broken_sentences(cleaned_lines)


def _join_broken_sentences(lines: list[str]) -> str:
    """Nối những dòng bị ngắt giữa câu thành câu hoàn chỉnh.

    Nguyên tắc: nếu một dòng không kết thúc bằng dấu câu (xem SENTENCE_ENDINGS)
    thì nó nhiều khả năng là một câu bị xuống dòng giữa chừng -> nối với dòng kế.

    Args:
        lines: Danh sách các dòng đã được làm sạch sơ bộ.

    Returns:
        Chuỗi text hoàn chỉnh, mỗi câu/đoạn nằm trên một dòng.
    """
    result: list[str] = []
    buffer = ""

    for line in lines:
        buffer = line if not buffer else f"{buffer} {line}"

        if buffer.rstrip().endswith(SENTENCE_ENDINGS):
            result.append(buffer.strip())
            buffer = ""

    if buffer.strip():
        result.append(buffer.strip())

    return "\n".join(result)


def main() -> None:
    """Điểm vào của script: đọc PDF -> (OCR nếu cần) -> làm sạch -> ghi file txt."""
    try:
        raw_text = extract_text_from_pdf(PDF_PATH)
        cleaned = clean_text(raw_text)

        if not cleaned.strip():
            raise RuntimeError(
                "Không trích xuất được nội dung nào từ PDF (kể cả sau khi OCR)."
            )

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(cleaned)

        char_count = len(cleaned)
        line_count = cleaned.count("\n") + 1
        print(
            f"[clean_data] ✅ Hoàn tất. Đã ghi {char_count} ký tự, "
            f"{line_count} dòng vào: {OUTPUT_PATH}"
        )
    except (FileNotFoundError, RuntimeError) as err:
        print(f"[clean_data] ❌ {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # noqa: BLE001 - bắt mọi lỗi còn lại để log rõ ràng.
        print(f"[clean_data] ❌ Lỗi không mong muốn: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

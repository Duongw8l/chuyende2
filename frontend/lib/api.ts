/**
 * Lớp giao tiếp với backend API.
 * URL backend ưu tiên đọc từ NEXT_PUBLIC_API_URL (build-time).
 * Nếu không có, fallback về backend production trên Railway để bản deploy
 * luôn chạy được kể cả khi biến build chưa được truyền vào.
 * Khi chạy local, đặt NEXT_PUBLIC_API_URL=http://localhost:8000 trong .env.local.
 */

// URL backend production (đổi nếu bạn deploy domain khác).
const DEFAULT_API_URL = "https://chuyende2-production.up.railway.app";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || DEFAULT_API_URL;

/** Kiểu dữ liệu response từ endpoint /chat. */
export interface ChatResponse {
  answer: string;
  sources: string[];
}

/**
 * Gửi câu hỏi tới backend và nhận câu trả lời.
 *
 * @param question - Câu hỏi của người dùng.
 * @returns Đối tượng gồm câu trả lời và danh sách nguồn trích dẫn.
 * @throws Error với thông điệp tiếng Việt thân thiện khi gọi API thất bại.
 */
export async function sendMessage(question: string): Promise<ChatResponse> {
  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    // Xử lý các mã lỗi HTTP cụ thể để báo cho người dùng dễ hiểu.
    if (!response.ok) {
      // Cố gắng đọc chi tiết lỗi do backend trả về.
      let detail = "Đã có lỗi xảy ra khi gọi máy chủ.";
      try {
        const errBody = await response.json();
        if (errBody?.detail) detail = errBody.detail;
      } catch {
        // Bỏ qua nếu body không phải JSON.
      }

      if (response.status === 429) {
        throw new Error("Bạn gửi quá nhanh. Vui lòng chờ một lát rồi thử lại.");
      }
      throw new Error(detail);
    }

    return (await response.json()) as ChatResponse;
  } catch (error) {
    // Lỗi mạng (backend tắt, sai URL...) sẽ rơi vào đây.
    if (error instanceof TypeError) {
      throw new Error(
        "Không kết nối được tới máy chủ. Hãy kiểm tra backend đã chạy chưa."
      );
    }
    // Ném lại các lỗi đã được chuẩn hoá ở trên.
    throw error;
  }
}

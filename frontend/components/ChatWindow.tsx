"use client";

import { useEffect, useRef, useState } from "react";
import { sendMessage } from "@/lib/api";
import ChatInput from "./ChatInput";
import MessageBubble, { Message } from "./MessageBubble";

// Tin nhắn chào mừng mặc định khi mở ứng dụng.
const WELCOME_MESSAGE: Message = {
  role: "bot",
  content:
    "Xin chào! Mình là gia sư Lịch sử 11. Hãy đặt câu hỏi về nội dung trong SGK nhé. 😊",
};

/**
 * Component trung tâm quản lý toàn bộ hội thoại:
 * - Lưu danh sách tin nhắn, trạng thái loading và lỗi.
 * - Gọi API backend qua sendMessage().
 * - Tự cuộn xuống tin mới nhất.
 */
export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tham chiếu tới đáy danh sách để auto-scroll.
  const bottomRef = useRef<HTMLDivElement>(null);

  // Mỗi khi messages/loading thay đổi -> cuộn xuống cuối.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  /**
   * Xử lý khi người dùng gửi câu hỏi:
   * 1. Thêm tin của user vào danh sách.
   * 2. Gọi API, hiển thị loading.
   * 3. Thêm câu trả lời của bot, hoặc hiển thị lỗi nếu thất bại.
   */
  const handleSend = async (question: string) => {
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setIsLoading(true);

    try {
      const res = await sendMessage(question);
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: res.answer, sources: res.sources },
      ]);
    } catch (err) {
      // Hiển thị banner lỗi và một tin nhắn xin lỗi từ bot.
      const msg =
        err instanceof Error ? err.message : "Đã có lỗi không xác định.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: "Xin lỗi, mình chưa trả lời được câu này. Vui lòng thử lại.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-md">
      {/* Khu vực hiển thị tin nhắn (cuộn được) */}
      <div className="chat-scroll flex-1 overflow-y-auto p-4">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}

        {/* Chỉ báo "bot đang gõ" khi đang chờ phản hồi */}
        {isLoading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      {/* Banner lỗi (nếu có) */}
      {error && (
        <div className="border-t border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
          ⚠️ {error}
        </div>
      )}

      {/* Ô nhập liệu */}
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}

/** Hiệu ứng 3 chấm nhấp nháy thể hiện bot đang soạn câu trả lời. */
function TypingIndicator() {
  return (
    <div className="mb-3 flex justify-start">
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3">
        <span className="h-2 w-2 animate-bounceDot rounded-full bg-slate-400 [animation-delay:-0.32s]" />
        <span className="h-2 w-2 animate-bounceDot rounded-full bg-slate-400 [animation-delay:-0.16s]" />
        <span className="h-2 w-2 animate-bounceDot rounded-full bg-slate-400" />
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";

interface ChatInputProps {
  // Hàm gửi câu hỏi, do component cha (ChatWindow) cung cấp.
  onSend: (text: string) => void;
  // Khoá input khi đang chờ bot trả lời.
  disabled: boolean;
}

/**
 * Ô nhập câu hỏi + nút gửi.
 * - Enter để gửi (Shift+Enter để xuống dòng).
 * - Tự xoá nội dung sau khi gửi.
 */
export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");

  // Xử lý gửi: bỏ qua nếu rỗng hoặc đang chờ phản hồi.
  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  // Cho phép gửi bằng Enter, xuống dòng bằng Shift+Enter.
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
      <textarea
        className="max-h-32 flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-100"
        rows={1}
        placeholder="Nhập câu hỏi về Lịch sử 11..."
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
        className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Gửi
      </button>
    </div>
  );
}

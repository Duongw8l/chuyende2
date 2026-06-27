/** Vai trò của một tin nhắn trong hội thoại. */
export type Role = "user" | "bot";

export interface Message {
  role: Role;
  content: string;
  sources?: string[];
}

/**
 * Bong bóng chat cho một tin nhắn.
 * - Tin của người dùng: căn phải, nền xanh.
 * - Tin của bot: căn trái, nền trắng, kèm nguồn trích dẫn (nếu có).
 */
export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 shadow-sm ${
          isUser
            ? "rounded-br-sm bg-blue-600 text-white"
            : "rounded-bl-sm border border-slate-200 bg-white text-slate-800"
        }`}
      >
        {/* Nội dung tin nhắn, giữ nguyên xuống dòng */}
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {/* Khối nguồn trích dẫn - chỉ hiển thị cho tin của bot khi có dữ liệu */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <details className="mt-2 text-xs text-slate-500">
            <summary className="cursor-pointer select-none hover:text-slate-700">
              📑 Nguồn trích dẫn ({message.sources.length})
            </summary>
            <ul className="mt-1 space-y-1 border-l-2 border-slate-200 pl-3">
              {message.sources.map((src, idx) => (
                <li key={idx} className="line-clamp-3">
                  {src}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

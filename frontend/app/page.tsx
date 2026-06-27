import ChatWindow from "@/components/ChatWindow";

/**
 * Trang chính - hiển thị tiêu đề và khung chat.
 * Đây là Server Component; mọi tương tác động nằm trong ChatWindow (client).
 */
export default function Home() {
  return (
    <main className="mx-auto flex h-screen max-w-3xl flex-col px-4 py-4">
      {/* Tiêu đề ứng dụng */}
      <header className="mb-3 text-center">
        <h1 className="text-2xl font-bold text-slate-800">
          📚 Gia sư Lịch sử 11
        </h1>
        <p className="text-sm text-slate-500">
          Hỏi đáp dựa trên SGK Lịch sử 11 — Kết nối tri thức với cuộc sống
        </p>
      </header>

      {/* Khung hội thoại chiếm phần còn lại của màn hình */}
      <ChatWindow />
    </main>
  );
}

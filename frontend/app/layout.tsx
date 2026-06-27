import type { Metadata } from "next";
import "./globals.css";

// Metadata mô tả trang (hiển thị trên tab trình duyệt & SEO cơ bản).
export const metadata: Metadata = {
  title: "Gia sư Lịch sử 11",
  description: "Chatbot RAG hỗ trợ học môn Lịch sử lớp 11 (SGK Kết nối tri thức).",
};

/**
 * Root layout - bọc toàn bộ ứng dụng.
 * Đặt ngôn ngữ tiếng Việt và nền gradient nhẹ cho toàn trang.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="bg-gradient-to-b from-slate-100 to-slate-200 text-slate-800 antialiased">
        {children}
      </body>
    </html>
  );
}

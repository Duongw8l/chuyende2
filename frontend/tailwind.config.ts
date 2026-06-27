import type { Config } from "tailwindcss";

/** Cấu hình Tailwind - khai báo các đường dẫn chứa class để tree-shake CSS. */
const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      keyframes: {
        // Hiệu ứng nhấp nháy cho dấu "đang gõ" của bot.
        bounceDot: {
          "0%, 80%, 100%": { transform: "scale(0)" },
          "40%": { transform: "scale(1)" },
        },
      },
      animation: {
        bounceDot: "bounceDot 1.4s infinite ease-in-out both",
      },
    },
  },
  plugins: [],
};

export default config;

# =====================================================================
# Dockerfile cho FRONTEND (Next.js App Router, output standalone).
# Multi-stage build để image cuối nhẹ nhất có thể.
# =====================================================================

# ---- Stage 1: Cài dependency ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# Dùng npm ci nếu có lock file, ngược lại dùng npm install.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---- Stage 2: Build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* phải có sẵn lúc build vì được nhúng vào bundle.
# Railway truyền biến này qua build arg.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ---- Stage 3: Runner (production) ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Tạo user không phải root cho an toàn.
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy output standalone + static assets.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# Railway cấp PORT động; server.js (standalone) đọc biến PORT.
# HOSTNAME=0.0.0.0 để server lắng nghe mọi interface (nếu chỉ localhost,
# Railway healthcheck từ bên ngoài sẽ không kết nối được).
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]

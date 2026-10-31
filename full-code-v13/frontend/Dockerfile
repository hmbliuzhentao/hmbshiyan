
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json ./

RUN npm install --no-audit --no-fund

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

# 单独检查 TypeScript，输出明确的错误信息
RUN echo "=== TYPECHECK BEGIN ===" \
    && ./node_modules/.bin/tsc --noEmit --pretty false \
    && echo "=== TYPECHECK PASSED ==="

# TypeScript 检查通过后才构建 Next.js
RUN npm run build

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER node

EXPOSE 3000

CMD ["node", "server.js"]

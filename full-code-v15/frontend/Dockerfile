FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
# Make ACR build robust even when a Git client omitted an empty public directory.
RUN mkdir -p /app/public
ENV NEXT_TELEMETRY_DISABLED=1
# Explicit diagnostics: TypeScript errors are printed separately from Next build.
RUN echo "=== TYPECHECK BEGIN ===" \
    && ./node_modules/.bin/tsc --noEmit --pretty false \
    && echo "=== TYPECHECK PASSED ==="
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]

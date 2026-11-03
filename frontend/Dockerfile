FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
# The original brand asset is mandatory. Never ship a release with a missing logo.
RUN test -s public/brand-logo.png || (echo "ERROR: required asset public/brand-logo.png is missing. Restore the original Black Mamba logo before building." >&2; exit 1)
ENV NEXT_TELEMETRY_DISABLED=1
RUN ./node_modules/.bin/tsc --noEmit --pretty false
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

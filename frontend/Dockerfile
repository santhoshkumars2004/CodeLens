# StackSense Frontend Dockerfile
# Multi-stage build: three stages keep the final image tiny (~150MB vs 1GB+)

# ══════════════════════════════════════════════════════════════════════
# Stage 1: DEPS — Install dependencies only
# Separate stage so Docker can cache node_modules independently of code
# ══════════════════════════════════════════════════════════════════════
FROM node:20-slim AS deps
WORKDIR /app

# Copy ONLY package files first (cache trick same as backend)
COPY package.json ./

# WHY npm install instead of npm ci?
# package-lock.json was created on WINDOWS — it resolves @tailwindcss/oxide
# to the Windows binary (oxide-win32-x64-msvc). Inside Docker (Linux Alpine),
# that binary doesn't exist. npm install re-resolves optional packages for
# the current platform (Linux musl), picking the correct Linux binary.
RUN npm install

# ══════════════════════════════════════════════════════════════════════
# Stage 2: BUILDER — Build the Next.js production bundle
# ══════════════════════════════════════════════════════════════════════
FROM node:20-slim AS builder
WORKDIR /app

# Copy node_modules from deps stage (no reinstall needed)
COPY --from=deps /app/node_modules ./node_modules

# Copy all source code
COPY . .

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Build Next.js — produces .next/standalone because of output: "standalone" in next.config.ts
# The standalone folder contains everything needed to run the app without node_modules
RUN npm run build

# ══════════════════════════════════════════════════════════════════════
# Stage 3: RUNNER — Minimal production image
# This is the ONLY stage that ends up in the final Docker image.
# Stages 1 and 2 are discarded — they were just build tools.
# Result: ~150MB instead of 1GB+
# ══════════════════════════════════════════════════════════════════════
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Run as non-root user (security best practice)
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy ONLY what's needed to run the app
# The [c] trick makes it a wildcard so Docker won't crash if the public folder doesn't exist
COPY --from=builder /app/publi[c] ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Start the standalone server (no node_modules needed!)
CMD ["node", "server.js"]

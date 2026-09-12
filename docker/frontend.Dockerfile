# syntax=docker/dockerfile:1.7
#
# Frontend image — Next.js 14 (App Router) on Node 20 LTS.
#
# Targets:
#   deps    dependency installation only, cached on the lockfile
#   dev     deps + source bind-mounted by compose, `next dev`
#   builder deps + source, produces the standalone production build
#   prod    minimal runtime carrying only the standalone output

# --------------------------------------------------------------------- deps
FROM node:20-alpine AS deps

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Lockfile-driven install, so the layer is cached until dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------- dev
FROM deps AS dev

ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ------------------------------------------------------------------ builder
FROM deps AS builder

ENV NODE_ENV=production
COPY frontend/ ./
RUN npm run build

# --------------------------------------------------------------------- prod
FROM node:20-alpine AS prod

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 --ingroup nodejs nextjs

# Standalone output carries its own minimal node_modules; static assets and the
# public directory are copied alongside it.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

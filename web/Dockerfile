# Production image of the web app (Next.js standalone server). Built on the server from a git clone.
# The browser only talks to this container; its /api rewrite forwards to the api container. That rewrite
# target is baked in at build time, so API_INTERNAL_URL is a build argument as well as a runtime variable.

FROM node:24.15.0-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24.15.0-bookworm-slim AS build
WORKDIR /app
ARG API_INTERNAL_URL
ENV API_INTERNAL_URL=${API_INTERNAL_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=1536
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN test -n "$API_INTERNAL_URL" && npm run build

FROM node:24.15.0-bookworm-slim AS runner
WORKDIR /app
ARG API_INTERNAL_URL
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    API_INTERNAL_URL=${API_INTERNAL_URL}
# Root-owned and read-only to the app user; the cache folder is a tmpfs in compose.prod.yaml.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
RUN mkdir -p .next/cache && chown node:node .next/cache
USER node
EXPOSE 3000
CMD ["node", "server.js"]

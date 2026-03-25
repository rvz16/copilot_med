# ── Build stage ──────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Set default env vars for the Vite build (since .env is in .dockerignore)
# Leave VITE_SESSION_MANAGER_URL empty to keep API requests same-origin and let
# Nginx proxy them to the backend container at runtime.
ARG VITE_USE_MOCK=true
ARG VITE_SESSION_MANAGER_URL=
ENV VITE_USE_MOCK=$VITE_USE_MOCK
ENV VITE_SESSION_MANAGER_URL=$VITE_SESSION_MANAGER_URL

RUN npm run build

# ── Production stage ─────────────────────────
FROM nginx:alpine

# Default upstream for API proxy
ENV SESSION_MANAGER_UPSTREAM=http://session-manager:8080

# Copy nginx config template
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine image uses envsubst on files in /etc/nginx/templates/
# automatically at startup, so SESSION_MANAGER_UPSTREAM is substituted.
CMD ["nginx", "-g", "daemon off;"]

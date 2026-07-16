FROM node:20-alpine as build-stage

WORKDIR /app

COPY package.json package-lock.json ./
# esbuild's postinstall validates its binary by exec-ing it right after
# writing it; under heavy build-host IO contention the file can still be
# open for write, yielding ETXTBSY ("text file busy"). The race is
# transient, so retry npm ci a couple of times before giving up.
RUN npm ci --no-audit --no-fund \
 || npm ci --no-audit --no-fund \
 || npm ci --no-audit --no-fund

COPY . .

# Umami analytics (public client-side id): Vite инлайнит env на этапе сборки,
# поэтому website-id "запекается" в index.html здесь. Пусто по умолчанию ->
# плагин ничего не инъектит. Значения приходят docker build-arg (CI:
# .github/workflows/deploy.yml из repo variables; on-server fallback:
# docker-compose build.args из .env).
ARG VITE_UMAMI_WEBSITE_ID=""
ENV VITE_UMAMI_WEBSITE_ID=$VITE_UMAMI_WEBSITE_ID
ARG VITE_UMAMI_SRC="/stats/script.js"
ENV VITE_UMAMI_SRC=$VITE_UMAMI_SRC
ARG VITE_SITE_URL=""
ENV VITE_SITE_URL=$VITE_SITE_URL

RUN npm run build

FROM nginx:stable-alpine as production-stage

COPY --from=build-stage /app/static/mini_app /usr/share/nginx/html/mini_app

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

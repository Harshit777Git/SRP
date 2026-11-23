FROM node:24-alpine AS build
ARG APP
WORKDIR /srv
COPY package*.json ./
RUN npm ci
COPY apps ./apps
ENV VITE_API_URL=/api
RUN npx vite build apps/${APP}/frontend --outDir /site
FROM nginx:alpine
COPY --from=build /site /usr/share/nginx/html
COPY docker/site.conf.template /etc/nginx/templates/default.conf.template

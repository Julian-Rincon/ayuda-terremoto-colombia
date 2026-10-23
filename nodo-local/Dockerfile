# Nodo Local (React + Vite). Build en Node, servido por nginx: la imagen
# final son archivos estáticos, sin Node ni node_modules adentro.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite congela las VITE_* en el bundle en tiempo de build, no de arranque:
# por eso la URL del Nodo Central entra como build arg.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.29-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

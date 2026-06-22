# Build Stage
FROM node:20 as build
WORKDIR /app
COPY package.json ./
RUN npm install -g vite@5.0.0
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

# Serve Stage
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

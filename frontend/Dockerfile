# Stage 1: Build the React Application
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve the Static Site via Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config if needed, or default is fine
EXPOSE 3000

# Override default Nginx port to 3000 to match compose setup
RUN sed -i 's/listen\(.*\)80;/listen 3000;/' /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]

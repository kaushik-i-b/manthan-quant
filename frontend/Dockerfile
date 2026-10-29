FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV ENGINE_URL=http://backend:8741
RUN npm run build
EXPOSE 8742
CMD ["npm", "run", "start"]

FROM node:24-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
USER node
EXPOSE 5173
CMD ["npm", "run", "dev"]

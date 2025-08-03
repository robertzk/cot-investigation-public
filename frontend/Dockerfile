FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

RUN npm install
RUN npm list react-router-dom

# Copy the rest of the application code
COPY . .

EXPOSE 3001

ENV NODE_ENV=development
ENV NODE_PATH=/app/node_modules

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "3001"]
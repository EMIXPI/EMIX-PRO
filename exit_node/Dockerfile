FROM node:20-alpine
WORKDIR /app
COPY package.json server.js ./
RUN npm install --omit=dev
EXPOSE 8080
ENV PORT=8080
CMD ["node", "server.js"]

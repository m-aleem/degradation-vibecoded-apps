FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

# Install ALL deps (including devDeps) because sequelize-cli is usually a devDependency
RUN npm ci || npm install

COPY . .

ENV NODE_ENV=production
EXPOSE 5000

# Run migrations using the local CLI, then start the server
CMD ["sh", "-lc", "./node_modules/.bin/sequelize db:migrate && node ./src/app.js"]

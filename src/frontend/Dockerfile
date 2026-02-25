FROM node:20-alpine

COPY . /app

WORKDIR /app

RUN yarn && yarn build && yarn build-server && rm -rf node_modules && yarn cache clean

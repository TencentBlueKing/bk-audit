FROM node:20-alpine

ENV NODE_OPTIONS=--max-old-space-size=4096

COPY . /app

WORKDIR /app

RUN yarn && yarn build && yarn build-server && rm -rf node_modules && yarn cache clean

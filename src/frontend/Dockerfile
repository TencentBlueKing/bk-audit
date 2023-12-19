FROM node:18.17.0

COPY . /app

WORKDIR /app

RUN yarn && yarn build && yarn build-server && rm -rf node_modules && yarn cache clean

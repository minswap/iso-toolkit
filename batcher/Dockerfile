FROM oven/bun

WORKDIR /batcher

COPY batcher/package.json /batcher/
COPY batcher/bun.lockb /batcher/

RUN bun install

ENV NODE_ENV=production

COPY batcher /batcher

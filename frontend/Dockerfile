FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY package-lock.json /app/package-lock.json
COPY next.config.ts /app/next.config.ts
COPY tsconfig.json /app/tsconfig.json
COPY src /app/src

RUN npm ci

ARG API_BASE_URL
ENV API_BASE_URL=$API_BASE_URL

ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE

RUN npm run build

EXPOSE 5173
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]

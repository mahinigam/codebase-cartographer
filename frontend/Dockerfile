FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY package-lock.json /app/package-lock.json
COPY next.config.ts /app/next.config.ts
COPY tsconfig.json /app/tsconfig.json
COPY src /app/src

RUN npm ci
RUN npm run build

EXPOSE 5173
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]

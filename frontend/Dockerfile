FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# NEXT_PUBLIC_* precisa estar disponível ANTES do build — é embutido no bundle
# do navegador em build-time, não lido em runtime do container.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV NODE_ENV=production
# Sem isso o server.js standalone pode bindar só na interface de loopback interna do
# container, inacessível via `-p 3000:3000` do host — sintoma clássico: container
# saudável mas "connection refused" do lado de fora.
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]

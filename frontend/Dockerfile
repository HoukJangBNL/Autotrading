# Frontend Dockerfile for React application
FROM node:18-alpine AS development

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application files
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "start"]

# Production build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application files
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine AS production

# Copy built files
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx configuration (server block)
COPY default.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
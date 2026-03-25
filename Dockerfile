# Production Dockerfile for Danecast Trades
# Builds frontend and backend together for Cloud Run deployment

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci --production=false

COPY frontend/ ./
RUN npm run build


# Stage 2: Python backend with frontend static files
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Copy frontend build from stage 1
COPY --from=frontend-builder /frontend/dist ./static

# Cloud Run sets PORT environment variable (default 8080)
ENV PORT=8080

EXPOSE 8080

# Run with production settings
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

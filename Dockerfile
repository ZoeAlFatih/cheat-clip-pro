# ==============================================================================
# Multi-stage Dockerfile for CheatClip Pro (React + Vite + FastAPI + FFmpeg)
# ==============================================================================

# ── Stage 1: Build React Frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build production bundle
COPY . .
RUN npm run build

# ── Stage 2: Runtime Environment (FastAPI + FFmpeg + Python) ──────────────────
FROM python:3.11-slim AS runner
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Install system dependencies (FFmpeg, essential libs for OpenCV/video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (use PyTorch CPU to keep image size small & fast on 4GB RAM)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# JavaScript runtime for yt-dlp's YouTube challenge solver (yt-dlp-ejs). yt-dlp needs deno >= 2.3
# or node >= 22; Debian's nodejs is 20, so ship the official deno binary.
COPY --from=denoland/deno:bin-2.9.7 /deno /usr/local/bin/deno

# Copy backend code
COPY backend ./backend

# Copy built frontend dist from Stage 1
COPY --from=frontend-builder /app/dist ./dist

# Run as an unprivileged user. Media directories are created here (owned by that user)
# so the named volumes in docker-compose.yml inherit the right ownership.
RUN useradd --create-home --uid 1000 app && \
    mkdir -p backend/temp_clips/uploads backend/exports backend/fonts && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Start Uvicorn ASGI Server
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

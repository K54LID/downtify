FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/downloads /app/logs

# yt-dlp auto-updates on every container start so it never goes stale.
# YouTube and other platforms change their APIs frequently — keeping
# yt-dlp current is the #1 fix for "downloads stopped working".
CMD ["sh", "-c", "pip install -U yt-dlp && alembic upgrade head && python -m app.main"]

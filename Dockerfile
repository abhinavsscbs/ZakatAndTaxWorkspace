FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
RUN useradd --system --create-home appuser && mkdir -p /app/storage && chown -R appuser:appuser /app
USER appuser
ENV PYTHONPATH=/app/backend DATA_DIR=/app/storage/data DEFAULT_OUTPUT_DIR=/app/storage/output DICTIONARY_FILE=/app/storage/replacement_dictionary.json LOG_DIR=/app/storage/logs OCR_LANG=eng+ara TESSERACT_CMD=/usr/bin/tesseract REQUIRE_AUTH=1
EXPOSE 10000
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 600 app:app"]

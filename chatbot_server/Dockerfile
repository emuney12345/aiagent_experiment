# chatbot-server/Dockerfile  (FULL FILE)

FROM python:3.11-slim

# ------------------------------------------------------------------
# 1)  Install system libs needed for:
#     • OpenCV  (libgl1)
#     • OCR     (tesseract-ocr + poppler-utils for UnstructuredPDFLoader)
# ------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# 2)  Set workdir and install Python deps
# ------------------------------------------------------------------
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------
# 3)  Copy application code and expose port
# ------------------------------------------------------------------
COPY . .

EXPOSE 8001

CMD ["uvicorn", "chatbot_server.main:app", "--host", "0.0.0.0", "--port", "8001"]

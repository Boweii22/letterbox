FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LETTERBOX_BIND=0.0.0.0 PORT=8080 LETTERBOX_DATA_DIR=/tmp/letterbox-data
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py sponsors.py public_server.py app.js interactions.js calendar.js sponsor-ui.js index.html style.css favicon.svg gemma_cloud.py ./
RUN useradd --create-home --uid 10001 letterbox
USER letterbox
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/health')"
CMD ["python", "public_server.py"]

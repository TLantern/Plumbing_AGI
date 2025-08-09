FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY Magiclink/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY Magiclink /app/Magiclink

ENV APP_BASE_URL=http://localhost:8000 \
    FRONTEND_ORIGIN=http://localhost:3000 \
    REDIS_URL=redis://redis:6379/0

EXPOSE 8000

CMD ["uvicorn", "Magiclink.magic:app", "--host", "0.0.0.0", "--port", "8000"] 
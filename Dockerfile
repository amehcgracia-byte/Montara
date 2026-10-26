FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/data MONTARA_DATA=/data
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY . /app
RUN groupadd -g 10001 montara && useradd -u 10001 -g montara -d /data montara && mkdir -p /data && chown montara:montara /data
USER 10001:10001
EXPOSE 8080
CMD ["gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "1800", "--access-logfile", "-", "deploy.entry:app"]

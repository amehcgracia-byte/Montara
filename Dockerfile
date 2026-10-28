FROM node:22-bookworm-slim AS download-runtime
RUN npm install --prefix /opt/download-runtime --no-audit --no-fund deno@2.5.6 \
    && /opt/download-runtime/node_modules/deno/deno --version

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/data MONTARA_DATA=/data
ARG MONTARA_BUILD_SHA=unknown
ARG MONTARA_ENGINE_SHA=unknown
ARG MONTARA_MIXER_SHA=unknown
ENV MONTARA_BUILD_SHA=$MONTARA_BUILD_SHA MONTARA_ENGINE_SHA=$MONTARA_ENGINE_SHA MONTARA_MIXER_SHA=$MONTARA_MIXER_SHA
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates ffmpeg fontconfig fonts-dejavu-core fonts-liberation2 \
    libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=download-runtime /opt/download-runtime/node_modules/deno/deno /usr/local/bin/deno
WORKDIR /app
COPY deploy/requirements-linux.lock /app/deploy/requirements-linux.lock
RUN pip install --no-cache-dir -r deploy/requirements-linux.lock
COPY . /app
RUN groupadd -g 10001 montara && useradd -u 10001 -g montara -d /data montara && mkdir -p /data && chown montara:montara /data
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -m deploy.healthcheck
CMD ["gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "1800", "--access-logfile", "-", "deploy.entry:app"]

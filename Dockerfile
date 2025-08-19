FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 
ENV PYTHONDONTWRITEBYTECODE=1



WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    netcat-openbsd  \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt



FROM python:3.12-slim AS runner


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_WORKER_CLASS="uvicorn.workers.UvicornWorker" \
    WEB_CONCURRENCY="2" \
    PORT="8082"


RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

ARG USERNAME=www
ARG UID=1000
ARG GID=1000

RUN groupadd --system --gid ${GID} appgroup && \
    useradd --system --create-home --uid ${UID} --gid appgroup ${USERNAME}


WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels


COPY . .

RUN chmod a+x wait-for-db.sh

RUN chown -R ${USERNAME}:appgroup /app

USER ${USERNAME}

EXPOSE 8082


CMD ["bash","-lc","exec gunicorn main:app -k ${UVICORN_WORKER_CLASS} -w ${WEB_CONCURRENCY} -b 0.0.0.0:${PORT} --access-logfile - --error-logfile -"]
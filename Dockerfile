FROM julia:1.12.6-bookworm@sha256:4979dc5c6fbcd7f5f0dc2ba2b336d136bda63a40c25e52a848222aa24326dfe1

ARG APP_VERSION=development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/web \
    JULIA_DEPOT_PATH=/opt/julia-depot \
    APP_VERSION=${APP_VERSION}

LABEL org.opencontainers.image.title="Prototipo Mamografico - Worker" \
      org.opencontainers.image.description="Worker Python y simulador Julia MPC" \
      org.opencontainers.image.revision="${APP_VERSION}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY web/requirements.lock.txt /tmp/requirements.lock.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /tmp/requirements.lock.txt \
    && python3 -m pip check

COPY simulator/Project.toml simulator/Manifest.toml /app/simulator/
COPY simulator/src /app/simulator/src
COPY simulator/scripts /app/simulator/scripts
RUN julia --project=/app/simulator -e "using Pkg; Pkg.instantiate(); Pkg.precompile()"

COPY . /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/runtime/uploads /app/storage/uploads \
    && chown -R app:app /app/runtime /app/storage /opt/julia-depot

USER app

EXPOSE 5000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "--config", "web/gunicorn.conf.py", "--chdir", "web", "wsgi:app"]

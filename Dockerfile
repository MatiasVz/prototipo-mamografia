FROM julia:1.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/web

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY web/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /tmp/requirements.txt

COPY simulator/Project.toml simulator/Manifest.toml /app/simulator/
COPY simulator/src /app/simulator/src
COPY simulator/scripts /app/simulator/scripts
RUN julia --project=/app/simulator -e "using Pkg; Pkg.instantiate(); Pkg.precompile()"

COPY . /app

RUN mkdir -p /app/storage/uploads

EXPOSE 5000

CMD ["python3", "web/run.py"]

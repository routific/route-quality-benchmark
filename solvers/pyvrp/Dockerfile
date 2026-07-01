# PyVRP is a library (not a server), so we wrap it in a tiny HTTP service.
FROM python:3.12-slim
WORKDIR /app
# PyVRP ships prebuilt wheels for x86_64 but not aarch64, so on ARM (e.g. Apple
# Silicon) pip compiles it from source with Meson — which needs a C++ toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY solve.py server.py .
EXPOSE 5002
CMD ["python3", "server.py"]

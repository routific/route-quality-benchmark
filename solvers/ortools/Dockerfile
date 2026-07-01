# OR-Tools ships prebuilt wheels (incl. aarch64), so no build toolchain needed.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY solve.py server.py .
EXPOSE 5001
CMD ["python3", "server.py"]

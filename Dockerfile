FROM python:3.12-slim AS dependencies
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -c requirements.lock fastapi uvicorn cryptography httpx mcp
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser:appuser /data
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

FROM dependencies AS api
COPY src /app/src
ENV CREDENTIALGATE_DATA_DIR=/data
USER appuser
EXPOSE 8010
CMD ["python", "-m", "uvicorn", "credentialgate.service:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]

FROM dependencies AS mcp
COPY src/credentialgate/__init__.py src/credentialgate/mcp_server.py src/credentialgate/client.py /app/src/credentialgate/
USER appuser
CMD ["python", "-m", "credentialgate.mcp_server"]

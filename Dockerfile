FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml requirements.lock.txt README.md ./
COPY epc ./epc
RUN pip install --no-cache-dir -r requirements.lock.txt \
    && pip install --no-cache-dir --no-deps .

ENV EPC_DATABASE=/app/data/full.sqlite
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "--factory", "epc.api:create_app", "--host", "0.0.0.0", "--port", "8000"]

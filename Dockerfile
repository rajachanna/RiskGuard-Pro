FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir . && \
  useradd --uid 10001 --create-home riskguard && \
  mkdir -p /data && chown riskguard:riskguard /data
USER riskguard
ENV RG_DB_PATH=/data/riskguard.sqlite
EXPOSE 8000
CMD ["uvicorn","riskguard.api:app","--host","0.0.0.0","--port","8000"]

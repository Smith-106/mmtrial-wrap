# mmtrial-wrap — CDP-attach variant.
# Requires a running RoxyBrowser profile with siftq.com open and CDP exposed.
# The container does NOT bundle a browser — it connects to the host's RoxyBrowser.

FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn[standard] python-multipart playwright>=1.63.0
COPY app ./app
ENV HOST=0.0.0.0 PORT=8080 CDP_HOST=host.docker.internal CDP_PORT=11611
EXPOSE 8080
CMD ["python", "-m", "app.main"]

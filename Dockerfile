# Two modes:
#   default  -> thin FastAPI wrapper; requires CF_CLEARANCE env or a writable
#               cookie file (bind-mount /data) supplied by you or your infra.
#   --build-arg AUTO_CLEARANCE=1 / full image -> additionally bundles headless
#               Chromium via Playwright so the service can self-refresh
#               cf_clearance when it expires (AUTO_CLEARANCE=1 at runtime).

ARG BASE=python:3.12-slim
FROM ${BASE} AS thin
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn[standard] python-multipart curl_cffi==0.16.3
COPY app ./app
VOLUME ["/data"]
ENV HOST=0.0.0.0 PORT=8080 CF_COOKIE_FILE=/data/cf_clearance.txt
EXPOSE 8080
CMD ["python", "-m", "app.main"]

# ---- full (auto-refresh) variant ----
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy AS full
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn[standard] python-multipart curl_cffi==0.16.3
COPY app ./app
VOLUME ["/data"]
ENV HOST=0.0.0.0 PORT=8080 CF_COOKIE_FILE=/data/cf_clearance.txt AUTO_CLEARANCE=1
EXPOSE 8080
CMD ["python", "-m", "app.main"]

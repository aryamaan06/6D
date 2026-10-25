FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SIXD_HOST=0.0.0.0 \
    SIXD_PORT=8080 \
    SIXD_STATE_ROOT=/var/lib/sixd \
    SIXD_LIVE_AI_ENABLED=0

WORKDIR /app
RUN groupadd --gid 10001 sixd \
    && useradd --uid 10001 --gid sixd --no-create-home sixd \
    && mkdir -p /var/lib/sixd \
    && chown 10001:10001 /var/lib/sixd

COPY src ./src
COPY tools/serve_hosted.py ./tools/serve_hosted.py
COPY examples ./examples
COPY design/vendor/lucide.min.js ./design/vendor/lucide.min.js

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request,urllib.parse; r=urllib.request.Request('http://127.0.0.1:8080/health',headers={'Host':urllib.parse.urlsplit(os.environ['SIXD_PUBLIC_ORIGIN']).netloc}); urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r,timeout=3).close()"]
CMD ["python", "tools/serve_hosted.py"]

# ---------------------------------------------------------------------------
# Stage 1: built-in models (YOLOX, Apache-2.0) converted to OpenVINO
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS models
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1
RUN pip install "openvino>=2025.3,<2026"
WORKDIR /build
# Optional: put yolox_*.onnx in ./modeller to avoid downloading during the build.
COPY modeller/ /build/modeller/
COPY tools/prepare_models.py .
ARG MODELS=yolox_tiny,yolox_s,yolox_m
RUN MODELS=${MODELS} python prepare_models.py /models 2>&1

# ---------------------------------------------------------------------------
# Stage 2: SynoArgus
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    SYNOARGUS_DATA=/data SYNOARGUS_MODELS=/models
# fonts-dejavu-core: labels on images. intel-opencl-icd: Intel iGPU support for OpenVINO.
RUN apt-get update && apt-get install -y --no-install-recommends \
      fonts-dejavu-core tzdata ocl-icd-libopencl1 intel-opencl-icd \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --from=models /models /models
COPY app ./app
LABEL org.opencontainers.image.title="SynoArgus" \
      org.opencontainers.image.description="AI object detection alerts for Synology Surveillance Station" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/mostlyflawles/synoargus"
VOLUME ["/data"]
EXPOSE 8686
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8686/api/state',timeout=4)" || exit 1
# No access log (the trigger token is part of the URL) and no blind trust in proxy headers (handled in the app).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8686", "--no-proxy-headers", "--no-access-log", "--no-server-header"]

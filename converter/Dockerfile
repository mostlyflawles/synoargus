# SynoArgus converter: own Ultralytics models (.pt) -> OpenVINO. Large image (PyTorch), only needed for own models.
FROM python:3.12-slim-bookworm
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 NO_COLOR=1 TERM=dumb
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install "ultralytics>=8.4" "openvino>=2025.3" "nncf>=2.14"
COPY tools/convert_models.py /convert_models.py
LABEL org.opencontainers.image.title="SynoArgus converter" \
      org.opencontainers.image.source="https://github.com/mostlyflawles/synoargus"
WORKDIR /work
CMD ["sh", "-c", "python /convert_models.py /in /out 2>&1"]

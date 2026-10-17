FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
# The v2 bundle embeds a frozen E5 encoder: everything loads from /opt/model, never the hub.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/api/src:/opt/runtime \
    SVO_MODEL_DIR=/opt/model SVO_DB_PATH=/data/observatory.sqlite \
    SVO_EXPECTED_MODEL_VERSION=svo-e2a46f504b19 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/hf TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
WORKDIR /opt/api
COPY app/server/requirements.lock /opt/api/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY training/src/svo/__init__.py training/src/svo/model.py training/src/svo/monitor.py training/src/svo/preprocessing.py training/src/svo/artifacts.py training/src/svo/data.py training/src/svo/v2.py /opt/runtime/svo/
COPY training/runs/v2/candidates/e5_tfidf/bundle/ /opt/model/
COPY app/server/src/ /opt/api/src/
COPY app/server/scripts/ /opt/api/scripts/
# Git cannot hold the 449 MB encoder weights; restore them at the pinned revision
# (hash-checked against the manifest) when the build context does not include them.
RUN HF_HUB_OFFLINE=0 HF_HOME=/tmp/hf-build python scripts/fetch_model_weights.py /opt/model \
    && rm -rf /tmp/hf-build \
    && python scripts/verify_runtime.py \
    && groupadd --gid 10001 svo \
    && useradd --uid 10001 --gid 10001 --no-create-home svo \
    && mkdir /data && chown 10001:10001 /data \
    && chmod -R a-w /opt/model /opt/runtime /opt/api
USER 10001:10001
EXPOSE 8000
# Cold start imports torch and loads the encoder (~25 s measured on a dev host).
HEALTHCHECK --interval=5s --timeout=3s --start-period=120s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
CMD ["python", "-m", "svo_api"]

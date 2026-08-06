#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-network-mvp:test}"
HOST_LM_URL="${HOST_LM_URL:-http://127.0.0.1:1234/v1}"
CONTAINER_LM_URL="${CONTAINER_LM_URL:-http://127.0.0.1:1234/v1}"
MODEL_NAME="${MODEL_NAME:-google/gemma-3n-e4b}"

echo "== build image =="
docker build -t "$IMAGE_NAME" .

echo
echo "== host check =="
echo "HOST_LM_URL=$HOST_LM_URL"
echo "MODEL_NAME=$MODEL_NAME"
curl -sv "${HOST_LM_URL%/v1}/health" || true
echo
curl -sv "$HOST_LM_URL/models" || true

echo
echo "== container check with host networking =="
echo "CONTAINER_LM_URL=$CONTAINER_LM_URL"
docker run --rm --network host \
  -e LM_URL="$CONTAINER_LM_URL" \
  -e MODEL_NAME="$MODEL_NAME" \
  "$IMAGE_NAME" \
  python -c '
import json
import os
import urllib.request

base = os.environ["LM_URL"].rstrip("/")
model = os.environ["MODEL_NAME"]

print("LM_URL:", base)
print("MODEL_NAME:", model)

print("\n--- models ---")
print(urllib.request.urlopen(base + "/models", timeout=10).read().decode())

payload = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
    "temperature": 0,
}).encode()

req = urllib.request.Request(
    base + "/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
)
print("\n--- chat/completions ---")
print(urllib.request.urlopen(req, timeout=30).read().decode())
'

echo
echo "== docker runner command check =="
python3 - <<'PY'
from app.config import AppConfig
from app.services.docker_runner import DockerRunner
import os

config = AppConfig.from_mapping(
    {
        "input_dir": "./data",
        "output_dir": "./output",
        "lmstudio_base_url": "http://host.docker.internal:1234/v1",
        "model_name": os.environ.get("MODEL_NAME", "google/gemma-3n-e4b"),
    }
)
print(DockerRunner().build_command(config))
PY

#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-network-mvp:test}"
LM_URL="${LM_URL:-http://127.0.0.1:1234/v1}"
MODEL_NAME="${MODEL_NAME:-google/gemma-3n-e4b}"

echo "== build image =="
docker build -t "$IMAGE_NAME" .

echo
echo "== host check =="
echo "LM_URL=$LM_URL"
echo "MODEL_NAME=$MODEL_NAME"
curl -sv "${LM_URL%/v1}/health" || true
echo
curl -sv "$LM_URL/models" || true

echo
echo "== container check with host networking =="
docker run --rm --network host \
  -e LM_URL="$LM_URL" \
  -e MODEL_NAME="$MODEL_NAME" \
  "$IMAGE_NAME" \
  python - <<'PY'
import json
import os
import sys
import urllib.request

base = os.environ["LM_URL"].rstrip("/")
model = os.environ["MODEL_NAME"]


def fetch(url, payload=None):
    try:
        if payload is None:
            req = urllib.request.Request(url)
        else:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"\n--- {url} -> {resp.status} ---")
            print(body[:4000])
            return resp.status, body
    except Exception as error:  # noqa: BLE001
        print(f"\n--- {url} -> ERROR ---")
        print(repr(error))
        return None, None


print("Python:", sys.version)
print("LM_URL:", base)
print("MODEL_NAME:", model)

fetch(base + "/models")
fetch(
    base + "/chat/completions",
    {
        "model": model,
        "messages": [
            {"role": "user", "content": "Reply with exactly: pong"}
        ],
        "temperature": 0,
    },
)
PY

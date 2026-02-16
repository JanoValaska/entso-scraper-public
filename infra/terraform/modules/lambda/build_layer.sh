#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MODULE_DIR"

rm -rf layer deps-layer.zip
mkdir -p layer/python

# Optionally allow overriding the build image (useful if you switch runtimes)
SAM_BUILD_IMAGE="${SAM_BUILD_IMAGE:-public.ecr.aws/sam/build-python3.13:latest}"

docker run --rm \
  --platform linux/amd64 \
  --user "$(id -u):$(id -g)" \
  --volume "$MODULE_DIR:/var/task" \
  --workdir /var/task \
  "$SAM_BUILD_IMAGE" \
  python -m pip install -r requirements-layer.txt -t layer/python

(cd layer && zip -rq ../deps-layer.zip .)

echo "Built: $MODULE_DIR/deps-layer.zip"

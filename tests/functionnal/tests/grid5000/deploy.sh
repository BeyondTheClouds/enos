#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR="${SCRIPT_DIR}/../../../.."

cd "$SCRIPT_DIR"


# shellcheck disable=SC1091
. ../utils.sh

virtualenv venv
# shellcheck disable=SC1091
. venv/bin/activate

pip install -e "$BASE_DIR"

echo "-ENOS DEPLOY-"
enos deploy -f grid5000.yaml
sanity_check "$BASE_DIR"
echo "-ENOS DESTROY-"
enos destroy

# Clean everything
echo "-ENOS DESTROY HARD-"
enos destroy --hard

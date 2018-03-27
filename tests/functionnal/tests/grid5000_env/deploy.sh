#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR="${SCRIPT_DIR}/../../../.."

cd "$SCRIPT_DIR"


# shellcheck disable=SC1091
. ../utils.sh

rm -rf venv
virtualenv venv
# shellcheck disable=SC1091
. venv/bin/activate

pip install -U pip

pip install -e "$BASE_DIR"

# pulling the images
enos up
enos kolla -- pull

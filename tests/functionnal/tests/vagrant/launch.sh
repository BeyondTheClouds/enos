#!/usr/bin/env bash

set -xe

if [[ -z "$1" ]]; then
    echo "Missing reservation file"
    echo "e.g: ./launch.sh <reservation file>"
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR="${SCRIPT_DIR}/../../../.."

cd $SCRIPT_DIR

# shellcheck disable=SC1091
. ../utils.sh

virtualenv venv
# shellcheck disable=SC1091
. venv/bin/activate

pip install -e "$BASE_DIR"
pip install -U -e /home/msimonin/workspace/repos/enoslib
pip install ipdb

# some cleaning
# vagrant destroy -f || true
enos up -f $1
enos os -vv
enos init
sanity_check "$BASE_DIR"
enos destroy
enos destroy --hard

#!/usr/bin/env bash

set -xe
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR="${SCRIPT_DIR}/../../../.."

cd $SCRIPT_DIR

# shellcheck disable=SC1091
. ../utils.sh

sudo ../vagrant_deps.sh
sudo ../enos_deps.sh

virtualenv venv
# shellcheck disable=SC1091
. venv/bin/activate

pip install -e "$BASE_DIR"

# some cleaning
vagrant destroy -f || true
enos deploy -f legacy_vbox.yaml
sanity_check "$BASE_DIR"
enos destroy
enos destroy --hard

#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

cd "$SCRIPT_DIR"

sudo ../vagrant_deps.sh

# Cleaning previous deployment if any
vagrant destroy -f || true
vagrant up && vagrant package
vagrant destroy -f

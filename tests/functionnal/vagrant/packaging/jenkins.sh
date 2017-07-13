#!/usr/bin/env bash

../vagrant_deps.sh

# Cleaning previous deployment if any
vagrant destroy -f
vagrant up && vagrant package

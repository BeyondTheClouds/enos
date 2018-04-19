#!/usr/bin/env bash

set -x

# this is a Jenkins slave dependency
apt-get update && apt-get install -y -t jessie-backports openjdk-8-jre

# Allow passwordless sudo to discovery
useradd -m -d /tmp/workspace ci
echo "ci    ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/ci
exec sudo -u ci java -jar /tmp/jenkins/slave.jar

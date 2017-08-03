#!/usr/bin/env bash

set -x

echo "deb http://http.debian.net/debian jessie-backports main" > /etc/apt/sources.list.d/jessie-backports.list
apt-get update && apt-get install -y -t jessie-backports openjdk-8-jre
update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java

# allow passwordless sudo to discovery

useradd -m -d /tmp/workspace ci
echo "ci    ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/ci
exec sudo -u ci java -jar /tmp/jenkins/slave.jar

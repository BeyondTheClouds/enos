#!/usr/bin/env bash

cat << EOF > /etc/motd

██╗      ███████╗███╗   ██╗ ██████╗ ███████╗      ██╗
╚██╗     ██╔════╝████╗  ██║██╔═══██╗██╔════╝     ██╔╝
 ╚██╗    █████╗  ██╔██╗ ██║██║   ██║███████╗    ██╔╝
 ██╔╝    ██╔══╝  ██║╚██╗██║██║   ██║╚════██║    ╚██╗
██╔╝     ███████╗██║ ╚████║╚██████╔╝███████║     ╚██╗
╚═╝      ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝      ╚═╝

Experimental eNvironment for OpenStack

---
Docs      - https://beyondtheclouds.github.io/enos/
Docker    - https://hub.docker.com/r/beyondtheclouds/
Discovery - https://beyondtheclouds.github.io/
Source    - https://github.com/BeyondTheClouds/enos
--- build date $(date)
EOF

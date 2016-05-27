#!/bin/bash
source var.sh
id -ur > DockerInstall/UID
exec $DOCKER_CMD build -t openwifiimage .

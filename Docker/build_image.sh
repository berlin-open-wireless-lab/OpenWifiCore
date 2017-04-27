#!/bin/bash
source var.sh
id -ur > DockerInstall/UID
source conf.sh
exec $DOCKER_CMD build -t openwifiimage . --build-arg=USE_LDAP=$USE_LDAP --build-arg=USE_AVAHI=$USE_AVAHI --build-arg=USE_DNSMASQ=$USE_DNSMASQ

#!/bin/bash
source ../var.sh

if [ "$#" -ne 1 ]; then
    echo "USAGE: $0 PATH_OR_URL_TO_IMAGE"
    echo "image is a (generic) rootfs .tar.gz"
    exit 1
fi

exec $DOCKER_CMD import "$1" lede_image

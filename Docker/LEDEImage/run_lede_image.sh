#!/bin/bash
source ../var.sh

exec $DOCKER_CMD run --name LEDEContainer lede_image /sbin/init

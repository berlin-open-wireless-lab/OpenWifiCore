#!/bin/bash

source var.sh
echo  \
"This runs (provisions) a container based on  an image, you can stop it later via 
        $DOCKER_CMD stop OpenWifi 
and start it again via 
        $DOCKER_CMD start OpenWifi"

exec $DOCKER_CMD run -P -p 6543:6543 -v $(dirname $PWD):/OpenWifi --name OpenWifi openwifiimage

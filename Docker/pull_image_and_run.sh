#!/bin/bash

source var.sh
echo  \
"This pulls (downloads) a recent image and runs (provisions) a container based on  an image, you can stop it later via 
        $DOCKER_CMD stop OpenWifiPull 
and start it again via 
        $DOCKER_CMD start OpenWifiPull"

THIS_USER_ID=$(id -ur)

$DOCKER_CMD pull openwifi/openwificore
exec $DOCKER_CMD run -P -p 6543:6543 -v $(dirname $PWD):/OpenWifi --name OpenWifiPull -e=OPENWIFI_UID=$THIS_USER_ID openwifi/openwificore

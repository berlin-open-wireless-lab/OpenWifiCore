#!/bin/bash

if [ ! -e /OpenWifi/setup.py ] && [ ! -e /home/openwifi/OpenWifi ]; then
    /DockerInstall/install_openwifi.sh
    return false
fi

if [ -e /home/openwifi/OpenWifi ]; then
    su openwifi -c "/home/openwifi/OpenWifi/Docker/DockerInstall/openwifi_update_plugins.sh"
    exec sudo -u openwifi /bin/bash - <<'    EOF'
        . /home/openwifi/venv/bin/activate
        if ! dpkg -s slapd &> /dev/null; then
            sed -i '/useLDAP/s/true/false/g' /home/openwifi/OpenWifi/development_listen_global.ini
        fi
        exec pserve /home/openwifi/OpenWifi/development_listen_global.ini
    EOF
else
        su openwifi -c"ln -s /OpenWifi /home/openwifi/OpenWifi"
        su openwifi -c". /home/openwifi/venv/bin/activate; cd /home/openwifi/OpenWifi; python setup.py develop; initialize_openwifi_db development.ini"
        return false
fi

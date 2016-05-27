#!/bin/bash

if [ -e /home/openwifi/OpenWifi ]; then
        su openwifi -c". /home/openwifi/venv/bin/activate; pserve /home/openwifi/OpenWifi/development_listen_global.ini"
else
        su openwifi -c"ln -s /OpenWifi /home/openwifi/OpenWifi"
        su openwifi -c". /home/openwifi/venv/bin/activate; cd /home/openwifi/OpenWifi; python setup.py develop; initialize_openwifi_db development.ini"
        return false
fi

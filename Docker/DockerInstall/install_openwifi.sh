#!/usr/bin/env bash

# install openwifi as openwifi user
su openwifi -c "cd ~; git clone git@github.com:berlin-open-wireless-lab/OpenWifiCore.git OpenWifi; cd OpenWifi; . ~/venv/bin/activate; python setup.py develop; initialize_openwifi_db development.ini"

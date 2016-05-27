#!/usr/bin/env bash

# install openwifi
#apt-get update
#apt-get -y install rabbitmq-server python3-pip git redis-server
#
#pip3 install virtualenv
#
#adduser \
#   --system \
#   --shell /bin/bash \
#   --gecos 'User for managing of openwifi' \
#   --group \
#   --disabled-password \
#   --home /home/openwifi \
#   openwifi

#cp /DockerInstall/openwifi-jobserver-beat.conf /etc/init
#cp /DockerInstall/openwifi-jobserver.conf /etc/init

# deploy keys
mkdir /home/openwifi/.ssh
chmod 700 /home/openwifi/.ssh
cp -rv /DockerInstall/deploy_keys/* /home/openwifi/.ssh/
chown -R openwifi:openwifi /home/openwifi/.ssh
chmod 600 /home/openwifi/.ssh/*

# install openwifi as openwifi user
su openwifi -c "cd ~; git clone git@gitlab.inet.tu-berlin.de:OpenWiFi/Controller.git OpenWifi; cd OpenWifi; . ~/venv/bin/activate; python setup.py develop; initialize_openwifi_db development.ini"

#start openwifi
#start openwifi-jobserver
#start openwifi-jobserver-beat



#!/usr/bin/env bash

# install openwifi
apt-get update
apt-get -y install rabbitmq-server python3-pip redis-server git

pip3 install virtualenv

adduser \
   --system \
   --shell /bin/bash \
   --gecos 'User for managing of openwifi' \
   --group \
   --uid $(cat /DockerInstall/UID) \
   --disabled-password \
   --home /home/openwifi \
   openwifi

#cp /DockerInstall/openwifi-jobserver-beat.conf /etc/init
#cp /DockerInstall/openwifi-jobserver.conf /etc/init


# install openwifi as openwifi user
su openwifi -c "cd ~; virtualenv venv;. ~/venv/bin/activate;pip install -r /DockerInstall/requirements.txt" #; python setup.py develop; initialize_openwifi_db development.ini" # cp /DockerInstall/openwifi.wsgi ."

#start openwifi
#start openwifi-jobserver
#start openwifi-jobserver-beat



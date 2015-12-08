#!/usr/bin/env bash

apt-get update
yes | apt-get install rabbitmq-server python3-pip git redis-server

pip3 install virtualenv

adduser \
   --system \
   --shell /bin/bash \
   --gecos 'User for managing of openwifi' \
   --group \
   --disabled-password \
   --home /home/openwifi \
   openwifi

cp /vagrant/openwifi*conf /etc/init

su openwifi -c "cd ~; git clone https://github.com/berlin-open-wireless-lab/wrtmgmt.git; cd wrtmgmt;cp /vagrant/development.ini .; virtualenv venv; . venv/bin/activate; pip install -r requirements.txt; python setup.py develop; initialize_openwifi_db development.ini"

start openwifi
start openwifi-jobserver
start openwifi-jobserver-beat

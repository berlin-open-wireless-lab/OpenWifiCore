openwifi
========

A management tool for OpenWrt devices.

[![Build Status](https://travis-ci.org/berlin-open-wireless-lab/OpenWifiCore.svg?branch=master)](https://travis-ci.org/berlin-open-wireless-lab/OpenWifiCore)

Getting Started
---------------

    sudo apt-get install rabbitmq-server python3-pip git redis-server
    git clone https://github.com/berlin-open-wireless-lab/wrtmgmt.git
    cd wrtmgmt
    pip3 install virtualenv
    virtualenv venv
    . venv/bin/activate
    pip install -r requirements.txt
    python setup.py develop
    initialize_openwifi_db development.ini
    echo development is ready now
  
    pserve  development.ini &
    celery -A openwifi.jobserver.tasks worker --loglevel=info
    celery -A openwifi.jobserver.tasks beat

Dependencies:
- rabbitmq <- for states and gearman jobs
- redis <- storing real-time information about nodes

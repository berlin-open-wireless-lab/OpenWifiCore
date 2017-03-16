#!/bin/bash

cd /home/openwifi
. venv/bin/activate

cd OpenWifi/Plugins

for plugin in *; do
    cd "$plugin"
    python setup.py develop
    cd ..
done

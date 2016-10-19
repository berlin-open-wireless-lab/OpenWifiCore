#!/bin/bash
if [ -e /home/openwifi/OpenWifi ]; then
        su openwifi -c". /home/openwifi/venv/bin/activate; cd ~; celery -A openwifi.jobserver.tasks beat"
else
        return false
fi

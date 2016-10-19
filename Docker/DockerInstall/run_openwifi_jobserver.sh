#!/bin/bash
if [ -e /home/openwifi/OpenWifi ]; then
        su openwifi -c". /home/openwifi/venv/bin/activate; cd ~; celery -A openwifi.jobserver.tasks worker --loglevel=info"
else
        return false
fi

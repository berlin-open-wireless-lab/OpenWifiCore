#!/bin/bash
if [ -e /home/openwifi/OpenWifi ]; then
        su openwifi -c""
    exec sudo -u openwifi /bin/bash - <<'    EOF'
        . /home/openwifi/venv/bin/activate
        cd ~
        exec celery -A openwifi.jobserver.tasks beat
    EOF
else
        return false
fi

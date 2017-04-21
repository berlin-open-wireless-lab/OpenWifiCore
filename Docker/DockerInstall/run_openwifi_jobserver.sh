#!/bin/bash
if [ -e /home/openwifi/OpenWifi ]; then
    exec sudo -u openwifi /bin/bash - <<'    EOF'
        . /home/openwifi/venv/bin/activate
        cd /home/openwifi
        exec celery -A openwifi.jobserver.tasks worker --loglevel=info
    EOF
else
        return false
fi

openwifi README
==================

Getting Started
---------------

- cd <directory containing this file>

- $venv/bin/python setup.py develop

- $venv/bin/initialize_openwifi_db development.ini

- $venv/bin/celery -A openwifi.jobserver.tasks worker

- $venv/bin/pserve development.ini

Dependencies:
- redis <- for states and gearman jobs
- influxdb <- for graphs


ubus 
uci

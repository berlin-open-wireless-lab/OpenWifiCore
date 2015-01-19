openwifi README
==================

Getting Started
---------------

   sudo apt-get install rabbitmq-server python3-pip git
   git clone https://github.com/berlin-open-wireless-lab/wrtmgmt.git
   cd wrtmgmt
   pip3 install virtualenv
   virtualenv venv
   . venv/bin/activate
   pip install -r requirements.txt
   python setup.py develop
   initialize_openwifi_db development.ini
   echo development is ready now

   pserve --monitor-restart --daemon development.ini
   celery -A tasks worker --loglevel=info

Dependencies:
- rabbitmq <- for states and gearman jobs


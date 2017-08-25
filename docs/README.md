# openwifi

## table of contents
[getting started using docker](#getting-started-using-docker)

[getting started manually](#getting-started-manually)

[API](#api)
* [nodes](#nodes)
* [user management](#user-management-and-access-control)
* [services](#services)
* [database queries](#db-queries)

A management tool for OpenWrt/LEDE devices.

## Getting Started

### Getting started using docker

There are docker images that will help you to getting started with OpenWifi. First of all clone the repo

    git clone https://github.com/berlin-open-wireless-lab/wrtmgmt.git

If you want to use the webviews clone them into the Plugin folder

    cd Plugins
    git clone https://github.com/berlin-open-wireless-lab/OpenWifiWeb.git
    cd ..

Then there are scripts that help downloading and starting the docker image:

    cd Docker
    ./pull_image_and_run.sh

When the scripts are finished you can use OpenWifi on localhost with port 6543.

The images mount the git repo - so you can easily make changes and try them out. The `ini-file` for the image is `development_listen_global.ini` in the repository root directory.

### Getting started manually

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

## API

This is a short overview about the rest-style API.

### Nodes

To list the UUIDs of all nodes just do a get to /nodes

    curl localhost:6543/nodes
    ["0a7b5cad-7435-95fb-1ba0-0242ac110003", "0a7b5cad-7435-95fb-1ba0-0242ac110004"]

To get all infos about a node do a get on `/nodes/UUID`

    curl localhost:6543/nodes/0a7b5cad-7435-95fb-1ba0-0242ac110003 | python -m json.tool 
    {
        "distribution": "LEDE",
        "name": "LEDE",
        "uuid": "0a7b5cad-7435-95fb-1ba0-0242ac110003",
        "configuration": { ... },
        "address": "172.17.0.3 ",
        "password": "59543c74cd26bbea",
        "login": "root",
        "configured": true,
        "version": "17.01-SNAPSHOT"
    }

You can add a new node by doing a POST to /nodes. To post a UUID is optional. Name, address, distribution, version, login and password are mandatory fields. The return code is the UUID of the new node.

    curl -H 'content-type: application/json' -X POST -d '{"name":"test","address":"127.0.0.1", "distribution":"LEDE", "version":"some version name", "login":"root", "password":"some password"}' localhost:6543/nodes
    "79926581-2cd0-52f6-bb8d-4e8ed33271b9"

In the same way you can change node parameters with doing a POST to `/nodes/UUID`. Furthermore you can delete a node by sending "DELETE" to `/nodes/UUID`.

You can display the changelog (how the configuration has been changed during syncing) with `/nodes/UUID/diff`

### User management and access control

To use the user management and access control it has to be enabled in the `ini file`. The key is called `"openwifi.useAuth"` and must be set to `"true"`. By default if no other user exists an admin user with the credentials admin:admin is created.

In order to change user data you have to login as an admin user:

    curl -c curl_cookies localhost:6543/login -d '{"login":"admin","password":"admin"}' -X POST  -H 'content-type: application/json'

Now you can list all users:

    curl -b curl_cookies localhost:6543/users
    {"admin": "465EWO"}

It lists the logins as keys with the user id as a value. You get more information about a user on `/users/USER_ID`:

    curl -b curl_cookies localhost:6543/users/465EWO
    {"admin": true, "login": "admin"}

### Services

### DB-Queries


## Plugins

### Available Plugins

### Architecture

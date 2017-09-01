# openwifi

## table of contents
[getting started using docker](#getting-started-using-docker)

[getting started manually](#getting-started-manually)

[API](#api)
* [nodes](#nodes)
* [user management](#user-management-and-access-control)
* [services](#services)
* [master configurations](#master-configurations)
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

This is a short overview about the rest-style API. It uses JSON as a serialization format.

### Nodes

To list the UUIDs of all nodes just do a `get` to /nodes

    curl localhost:6543/nodes
    ["0a7b5cad-7435-95fb-1ba0-0242ac110003", "0a7b5cad-7435-95fb-1ba0-0242ac110004"]

To get all infos about a node do a `get` to `/nodes/UUID`

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

You can add a new node by doing a `post` to /nodes. The `UUID`-key is optional. Name, address, distribution, version, login and password are mandatory fields. The return code is the UUID of the new node.

    curl -H 'content-type: application/json' -X POST -d '{"name":"test","address":"127.0.0.1", "distribution":"LEDE", "version":"some version name", "login":"root", "password":"some password"}' localhost:6543/nodes
    "79926581-2cd0-52f6-bb8d-4e8ed33271b9"

In the same way you can change node parameters with doing a `post` to `/nodes/UUID`. Furthermore you can delete a node by sending `delete` to `/nodes/UUID`.

You can display the changelog (how the configuration has been changed during syncing) by doing a `get` to `/nodes/UUID/diff`.

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


Access to nodes is granted by access objects. You can create new ones by doing a `post` to `/access`. In the post you need to provide a JSON-Object with the following optional fields:

| Key name              | description                                              |
|-----------------------|----------------------------------------------------------|
| `userid`              | id of the user to add to the access object               |
| `apikeyid`            | id of the apikey to add to the access object             |
| `data`                | actual access data - more on that below                  |
| `access_all_nodes`    | a boolean indicating that access is allowed to all nodes |

The data field is a list of JSON-objects with the following fields:

| Key name              | description                                                         |
|-----------------------|---------------------------------------------------------------------|
| `type`                | either "pathstring" or "query"                                      |
| `access`              | required if type is "pathstring" values are rw, ro or none          |
| `string`              | required if type is "pathstring" - the actual path                  |
| `query`               | required if type is "query" - the query (see [below](#db-queries)) that is allowed |

### Services

Another program can subscribe to OpenWifi to automatically change configuration options if the node matches certain criteria. To do so it has to provide a shell script that is run on the node and the output (stdout) is compared to a match string. If both match the node gets the name of the service as a capability. If the node has the name of the service as a capability the list of queries is run on the node.

You can add a service by doing a `post` to `/service` with the following options:

| Key name             | description                                                         |
|----------------------|---------------------------------------------------------------------|
| `name`               | the name of the service and the capability                          |
| `queries`            | a list of queries (see [below](#db-queries))                        |
| `capability_script`  | the shell script that is run on the node (commands)                 |
| `capabaility_match`  | the string the shell script has to match                            |

As usual you get a list of registered services by doing a `get` to `/service` and can modify and delete services with a `post` or a `delete` to `/service/SERVICE_ID`.

## Master Configurations

Master configurations are the representation of the graph configuration model. A master configuration is associated with a node and contains all configurations and links between the configuration. To list all master configurations do a `get` to `/masterConfig` - it will return a list of JSON-Objects with the `id` and its associated nodes (`assoc`) as keys. 

If you do a `get` to `/masterConfig/ID` it will return a JSON-Object with a list of the vertices (key is `nodes`) and edges (key is `edges`) of the graph representation. If you do a `delete` it will delete the master configuration.

A `get` to `/masterConfig/ID/json` will return a UCI compatible JSON-Object.

### DB-Queries

Queries are the way to display or change values from the configuration database. The endpoint is `/masterConfig/ID/query`. It has the following keys:

|Key            | Value                                                                                                                                   |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------|
|`package`      | optional package name                                                                                                                   |
|`name`         | optional config name                                                                                                                    |
|`type`         | optional config type                                                                                                                    |
|`matchOptions` | optional dict of option-value pairs to match, dot is possible like in option, use null if you just want to check if the option exists   |
|`option`       | optional option name, it is possible to go though a link with dots like: linkname.option                                                |
|`set`          | optional set option to this value                                                                                                       |
|`add_config`   | add config, type and package are mandatory for new configs, use either "new" for a new config, "new-nonexistent" to just create if no other exists, or a node-id to add a config |
|`add_options`  | optional dict of key-value pairs that should be added to found configs                                                                  |
|`del_options`  | optional list of options to remove                                                                                                      |

A query works in the way that it first filters all configurations according to a criteria (like `package`, `name`, `type`, `matchOptions`). If you add `option` the option value is returned or you can change it's value with `set`. You can also add options (`add_options`) or delete (`del_options`) them. You can also add a configuration with the given matching criteria (`add_config`).

## Plugins

Plugins are realized by having special named [entry points](https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins). There is [an example plugin](https://github.com/berlin-open-wireless-lab/OpenWifiExamplePlugin) that demonstrates the possible functionality.

To use plugins with the docker images: just clone the repository into the `Plugins` folder and restart the image.

### Available Plugins

#### [OpenWifiExamplePlugin](https://github.com/berlin-open-wireless-lab/OpenWifiExamplePlugin)

This Plugin demonstrates  how to implement a plugin.

#### [OpenWifiWeb](https://github.com/berlin-open-wireless-lab/OpenWifiWeb)

This Plugin adds web views to the OpenWifiCore application.

#### [OpenWifiLocation](https://github.com/berlin-open-wireless-lab/OpenWifiLocation)

This Plugin implements a geolocation lookup via GoogleGeo API with the help of a scan of nearby SSIDs.

#### [OpenWifiIcinga](https://github.com/berlin-open-wireless-lab/OpenWifiIcinga)

This Plugin registers a node to [icinga](https://www.icinga.com/) for monitoring.

#### [OpenWifiTemplates](https://github.com/berlin-open-wireless-lab/OpenWifiTemplates)

This adds the old templating system to OpenWifi.

### Architecture

As stated previously the plugins are realized by special entry points. The entry point group is `OpenWifi.plugin`. See also the [setup.py of the example plugin](https://github.com/berlin-open-wireless-lab/OpenWifiExamplePlugin/blob/master/setup.py). The following subsections explain the entry points and what they do in more details.

#### Routes and global views

If you want to register new routes in your plugin you have to point the entry point `addPluginRoutes` to a method that gets the pyramid `config` object as a parameter.

Example from the example Plugin:
```python
def addPluginRoutes(config):
    config.add_route('testplugin', '/testplugin')
    config.add_route('testplugin_assign', '/testplugin/add/{uuid}')
    return "Testplugin"
```

The return string is used for logging purposes. If you want to register views to the main menu you need the `globalPluginViews` entry point. This points to a list of views you want to register. The views you want to register are made up of a list containing the route name and the displayed name in the menu.

Example from the example Plugin:
```python
globalTestpluginViews = [['testplugin', 'Testplugin']]
```

#### Tasks

#### Database Models

#### Action on device registration

#### Communication

Communication uses a abstract class to define class methods that are invoked when OpenWifi tries to communicate with the node. This is the abstract class:

```python
class OpenWifiCommunication(metaclass=ABCMeta):

    @ClassProperty
    @classmethod
    def string_identifier_list(self): pass

    @abstractclassmethod
    def get_config(self, device, DBSession): pass

    @abstractclassmethod
    def update_config(self, device, DBSession): pass

    @abstractclassmethod
    def update_status(self, device, redisDB): pass

    @abstractclassmethod
    def update_sshkeys(self, device, DBSession): pass

    @abstractclassmethod
    def exec_on_device(self, device, DBSession, cmd, prms): pass
```

The string identifier acts as a way to determine if this class should use for the node for communication and must therefore match the node's `communication_protocol` property.

import transaction
from pyramid_rpc.jsonrpc import jsonrpc_method
from sqlalchemy.sql.expression import func as sql_func

from pyuci import Uci

from openwifi.models import (
    AccessPoint,
    DBSession,
    OpenWrt,
    Configuration,
    ConfigurationLink,
    MasterConfiguration)

import json

from openwifi.utils import diffChanged
from openwifi.authentication import get_node_by_request

def getMaxId(dbObject): # object needs to have an integer field named id
    query = DBSession.query(sql_func.max(dbObject.id)) 
    try: 
        max = int(query[0][0])
    except:
        max = 0

def updateDeviceConfig(masterConfig):
    for device in masterConfig.openwrt:
        uci_conf = Uci()
        uci_conf.load_tree(device.configuration)

        diff = masterConfig.exportUCI().diff(uci_conf)

        if diffChanged(diff):
            device.configuration = masterConfig.exportJSON()

def updateMasterConfig(device, newJsonString):
    uci_conf = Uci()
    uci_conf.load_tree(newJsonString)

    if not device.masterconf:
        newMasterConf = masterConfigFromUci(uci_conf)
        newMasterConf.openwrt.append(device)
        return

    diff = device.masterconf.exportUCI().diff(uci_conf)

    if diffChanged(diff):
        newMasterConf = masterConfigFromUci(uci_conf)
        if device.masterconf:
            deleteMasterConf(device.masterconf)
        newMasterConf.openwrt.append(device)

def parseToDBModel(device):
    uci_conf = Uci()
    uci_conf.load_tree(device.configuration)

    newMasterConf = masterConfigFromUci(uci_conf)
    newMasterConf.openwrt.append(device)

def masterConfigFromUci(uci_conf):
    dict_of_configs = {}
    newMasterConf = MasterConfiguration(getMaxId(MasterConfiguration))

    for packagename, package in uci_conf.packages.items():
        for confname, conf in package.items():
            newConf = Configuration(getMaxId(Configuration))
            newConf.package = package.name
            newConf.name = confname
            newConf.data = json.dumps(conf.export_dict(forjson=True))
            key = (packagename, confname)
            if key not in dict_of_configs.keys():
                dict_of_configs[key] = []
            dict_of_configs[key].append(newConf)

    for packagename, package in uci_conf.packages.items():
        for confname, conf in package.items():
            for option, value in conf.keys.items():
                foundItem = None
                if (conf.uci_type == "dhcp" and option == "interface"):
                    networkpackage = uci_conf.packages['network']
                    if value in networkpackage.keys():
                        foundItem = ('network', value)
                elif (conf.uci_type == "zone" and option == "name") or \
                     (conf.uci_type == "dnsmasq" and option == "domain"):
                    #ignore these options
                    pass
                elif packagename ==  "firewall" and  \
                     (option == "src" or option == "dest"): 
                    #search in firewall zones
                    firewall_package = uci_conf.packages['firewall']
                    for configname, firewall_conf in firewall_package.items():
                        if firewall_conf.uci_type == "zone" and firewall_conf.keys['name'] == value:
                            foundItem = ('firewall', configname)
                            break
                else:
                    if isinstance(value, list):
                        for item in value:
                            for entry in dict_of_configs.keys():
                                if entry[1] == item:
                                    foundItem = entry #assume it is just once in a list
                    else:
                        for entry in dict_of_configs.keys():
                            if entry[1] == value:
                                foundItem = entry
                if foundItem:
                    possibleConfigs = []

                    for config in dict_of_configs[foundItem]:
                        parsedData = json.loads(config.data)
                        if parsedData['.type'] != "dhcp":
                            possibleConfigs.append(config)

                    if possibleConfigs:
                        newLink = ConfigurationLink(getMaxId(ConfigurationLink))

                        for config in possibleConfigs:
                            newLink.to_config.append(config)

                        newLink.data = option
                        key = (packagename, confname)
                        for config in dict_of_configs[key]:
                            config.to_links.append(newLink)
                        newLink.masterconf = newMasterConf

    for confname, conflist in dict_of_configs.items():
        for config in conflist:
            newMasterConf.configurations.append(config)

    return newMasterConf

def deleteMasterConf(masterConf):
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker()
    session = Session.object_session(masterConf)

    for conf in masterConf.configurations:
        for link in conf.to_links:
            session.delete(link)
        session.delete(conf)
    session.delete(masterConf)

def get_node_id(node):
    typePrefix = '?'
    if isinstance(node, Configuration):
        typePrefix = 'c'
    elif isinstance(node, ConfigurationLink):
        typePrefix = 'l'
    return typePrefix+str(node.id)

def get_node_name(node):
    if isinstance(node, Configuration):
        jsonData = json.loads(node.data)
        return node.name + " (" + jsonData['.type'] + ")"
    if isinstance(node, ConfigurationLink):
        return node.data

def getMConfigGraph(mconfig):
    nodesList = mconfig.configurations
    visited = []
    graph = { "nodes" : [],
              "edges" : [] }

    # add master and first config nodes
    graph['nodes'].append({ 'id'   : "mc",
                            'label' : "master"})
    for node in nodesList:
        if not node.from_links: # if node has no links to it, it is a top level node
            graph['edges'].append({'from' : 'mc',
                                   'to'   : get_node_id(node)})
        graph['nodes'].append( {'id'   : get_node_id(node),
                                'label' : get_node_name(node)})

    linksList = mconfig.links

    for link in linksList:
        graph['nodes'].append( {'id'   : get_node_id(link),
                                'label' : get_node_name(link)})

        for config in link.to_config:
            graph['edges'].append({'from' : get_node_id(link),
                                   'to'   : get_node_id(config)})

        for config in link.from_config:
            graph['edges'].append({'from' : get_node_id(config),
                                   'to'   : get_node_id(link)})
        
    return graph

# TODO remove or transform into rest
@jsonrpc_method(method='get_config_graph', endpoint='api')
def device_get_config_graph(request, uuid):
    device = DBSession.query(OpenWrt).get(uuid)
    masterConf = device.masterconf
    return getMConfigGraph(masterConf)

from cornice import Service

# just checks if the master config is assigned to node that is accessible by the user/apikey
# TODO: add more security and check if sane parameters are used
def validate_masterconfig(request, **kwargs):
    mconfID = request.matchdict['ID']
    masterConfig = DBSession.query(MasterConfiguration).get(mconfID)

    request.masterConfig = masterConfig

    if user_is_not_allowed_to_user_master_config(request, masterConfig):
        request.errors.add('', 'access dienied', 'user is not allowed to change this master config')

def user_is_not_allowed_to_user_master_config(request, maserconf):
    from openwifi.authentication import get_nodes
    nodes = get_nodes(request)

    if all(ow in nodes for ow in masterConfig.openwrt):
        return False
    else:
        return True

parseDB = Service(name='parseDB',
                  path='/parse/{UUID}',
                  description='parseNodeWithUUID',
                  factory='openwifi.node_context',
                  permission='node_access')

@parseDB.get()
def get_parseDB(request):
    device = get_node_by_request(request)

    if not device:
        return False

    parseToDBModel(device)
    return True

deleteMasterConfig = Service(name='deleteMasterConfig',
                             path='/node/{UUID}/deleteMasterConfig',
                             description='delete MasterConfig of a given node',
                             factory='openwifi.node_context',
                             permission='node_access')

@deleteMasterConfig.get()
def get_delMasterConfig(request):
    device = get_node_by_request(request)

    if not device:
        return False

    deleteMasterConf(device.masterconf)

    return True

listMasterConfigs = Service(name='ListMasterConfigs',
                           path='/masterConfig',
                           description='list master config ids and assoc nodes')

@listMasterConfigs.get()
def get_listMasterConfigs(request):
    result = []
    for mconfig in DBSession.query(MasterConfiguration):
        if user_is_not_allowed_to_user_master_config(request, mconfig):
            continue

        temp = {}
        temp["id"] = mconfig.id
        temp["assoc"] = []
        for ap in mconfig.openwrt:
            temp["assoc"].append(str(ap.uuid))
        result.append(temp)
    return result

manageMasterConfig = Service(name='ManageMasterConfig',
                             path='/masterConfig/{ID}',
                             description='manage given MasterConig',
                             validators=(validate_masterconfig,))

@manageMasterConfig.get()
def get_manageMasterConfig(request):
    id = request.matchdict['ID']
    masterconf = DBSession.query(MasterConfiguration).get(id)
    return getMConfigGraph(masterconf)

@manageMasterConfig.delete()
def delete_manageMasterConfig(request):
    id = request.matchdict['ID']
    masterconf = DBSession.query(MasterConfiguration).get(id)

    if not masterconf:
        return False

    deleteMasterConf(masterconf)

    return True

masterConfigJSON = Service(name='MasterConfigJSON',
                           path='/masterConfig/{ID}/json',
                           description='print given MasterConig as json',
                           validators=(validate_masterconfig,))

@masterConfigJSON.get()
def getMasterConfigJSON(request):
    id = request.matchdict['ID']
    masterconf = DBSession.query(MasterConfiguration).get(id)
    if not masterconf:
        return False
    return json.loads(masterconf.exportJSON())

queryMasterConfig = Service(name='QueryMasterConfig',
                            path='/masterConfig/{ID}/query',
                            description='get an option key of a masterConfig',
                            validators=(validate_masterconfig,))

@queryMasterConfig.get()
def get_queryMasterConfig(request):
    usage = {'package' : 'optional package name',
             'name'    : 'optional config name',
             'type'    : 'optional config type',
             'matchOptions' : 'optional dict of option-value pairs to match, dot is possible like in option, use null if you just want to check of the option exists',
             'option'  : 'optional option name, it is possible to go though a link with dots like: linkname.option',
             'set'     : 'optional set option to this value',
             'add_options' : 'optional dict of key-value pairs that should be added to found configs',
             'del_options' : 'optional list of options to remove'}
    return usage

@queryMasterConfig.post()
def post_queryMasterConfig(request):
    query = request.json_body

    return query_master_config(query, request.masterConfig)

def query_master_config(query, master_config):
    configs = master_config.configurations
    configs = filter_configs(configs, query)

    if 'option' in query:
        options = query['option']
    else:
        options = False

    result = {'values' : [],
              'added' : [],
              'deleted' : []}

    for config in configs:
        if options:
            curConf, option = follow_options_path(config, options)
            curConfData = json.loads(curConf.data)
            value = curConfData[option]

            if 'set' in query.keys():
                curConfData[option] = query['set']
                result['values'].append({'from' : value, \
                                         'to'   : query['set']})
            else:
                result['values'].append(value)
        else:
            curConf = config
            curConfData = json.loads(curConf.data)

        if 'add_options' in query:
            for k, v in query['add_options'].items():
                curConfData[k] = v
                result['added'].append({k:v})

        if 'del_options' in query:
            for opt in query['del_options']:
                try:
                    result['deleted'].append({opt:curConfData.pop(opt)})
                except KeyError:
                    pass

        if 'del_options' in query.keys() or \
           'add_options' in query.keys() or \
           'set' in query.keys():
            curConf.data = json.dumps(curConfData)

    #TODO: maybe just do this if it is necessary
    updateDeviceConfig(master_config)

    return result

def filter_configs(configs, query):
    if 'package' in query:
        package = query['package']
        configs = filter_configs_by_package(configs, package)

    if 'name' in query:
        name = query['name']
        configs = filter_configs_by_name(configs, name)

    if 'type' in query:
        type = query['type']
        configs = filter_configs_by_type(configs, type)

    if 'matchOptions' in query:
        match_options = query['matchOptions']
        configs = filter_configs_by_match_options(configs, match_options)

    return configs

def filter_configs_by_package(configs, package):
    result = []
    for config in configs:
        if config.package == package:
            result.append(config)
    return result

def filter_configs_by_name(configs, name):
    result = []
    for config in configs:
        if config.name == name:
            result.append(config)
    return result

def filter_configs_by_type(configs, type):
    result = []
    for config in configs:
        configData = json.loads(config.data)
        if configData['.type'] == type:
            result.append(config)
    return result

def filter_configs_by_match_options(configs, match_options):
    result = []

    for config in configs:
        doesMatch = False
        for key, value in  matchOptions.items():
            try:
                curConf, option = follow_options_path(config, key)
                configData = json.loads(curConf.data)
                if (option in configData.keys() and 
                    (value == configData[option] or value == None)):
                    doesMatch = True
                else:
                    doesMatch = False
                    break
            # an exception might occur if we try to 
            # find a subconfig that doesn't exist
            except:
                doesMatch = False
                break
        if doesMatch:
            result.append(config)

    return result

def follow_options_path(config, options):
    curConf = config
    optionList = options.split('.')
    option = optionList[-1]
    # TODO: handle multiple links?
    for i in range(len(optionList)-1):
        curConf = curConf.getLinkByName(optionList[i]).to_config[0]
    return curConf, option

def config_to_path(config):
    # TODO: handle multiple links?
    path = "." + config.name + ' (' + config.get_type() + ')'
    while config.from_links:
        path += "." + config.from_links[0].data
        config = config.from_links[0].from_config[0]
        path += "." + config.name + ' (' + config.get_type() + ')'

    return path[1:]

def validate_config_node_access(request, **kwargs):
    node = request.matchdict['NODE']

    if node[0] == 'l':
        link = DBSession.query(ConfigurationLink).get(node[1:])
        if user_is_not_allowed_to_user_master_config(request, link.masterconf):
            request.error.add('', 'access denied', 'access to this master config was denied')
            return

        result = {"link": link.data}

    if node[0] == 'c':
        conf = DBSession.query(Configuration).get(node[1:])
        if user_is_not_allowed_to_user_master_config(request, conf.masterconf):
            request.error.add('', 'access denied', 'access to this master config was denied')
            return

        result = {"conf": json.loads(conf.data)}

    if not result:
        request.error.add('querystring', 'not found', "couldn't find a matching node")

    request.nodeData = result


masterConfNodeInfo = Service(name='MasterConfNodeInfo',
                             path='/masterConfigNodeInfo/{NODE}',
                             description='get node data',
                             validators=(validate_config_node_access,))

@masterConfNodeInfo.get()
def get_master_conf_node_info(request):
    return request.nodeData

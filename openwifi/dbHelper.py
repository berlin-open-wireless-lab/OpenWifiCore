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

def getMaxId(dbObject): # object needs to have an interger field named id
    query = DBSession.query(sql_func.max(dbObject.id)) 
    try: 
        max = int(query[0][0])
    except:
        max = 0

def parseToDBModel(device):
    uci_conf = Uci()
    uci_conf.load_tree(device.configuration)
    dict_of_configs = {}

    newMasterConf = MasterConfiguration(getMaxId(MasterConfiguration))
    newMasterConf.openwrt.append(device)
    DBSession.add(newMasterConf)

    for packagename, package in uci_conf.packages.items():
        for confname, conf in package.items():
            newConf = Configuration(getMaxId(Configuration))
            DBSession.add(newConf)
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
                        DBSession.add(newLink)

    for confname, conflist in dict_of_configs.items():
        for config in conflist:
            newMasterConf.configurations.append(config)

def deleteMasterConf(masterConf):
    for conf in masterConf.configurations:
        for link in conf.to_links:
            DBSession.delete(link)
        DBSession.delete(conf)
    DBSession.delete(masterConf)

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

@jsonrpc_method(method='get_config_graph', endpoint='api')
def device_get_config_graph(request, uuid):
    device = DBSession.query(OpenWrt).get(uuid)
    masterConf = device.masterconf
    return getMConfigGraph(masterConf)

from cornice import Service

parseDB = Service(name='parseDB',
                  path='/parse/{UUID}',
                  description='parseNodeWithUUID')

@parseDB.get()
def get_parseDB(request):
    uuid = request.matchdict['UUID']
    device = DBSession.query(OpenWrt).get(uuid)

    if not device:
        return False

    parseToDBModel(device)
    return True

deleteMasterConfig = Service(name='deleteMasterConfig',
                             path='/node/{UUID}/deleteMasterConfig',
                             description='delete MasterConfig of a given node')

@deleteMasterConfig.get()
def get_delMasterConfig(request):
    uuid = request.matchdict['UUID']
    device = DBSession.query(OpenWrt).get(uuid)

    if not device:
        return False

    deleteMasterConf(device.masterconf)

    return True

listMasterConfigs= Service(name='ListMasterConfigs',
                           path='/masterConfig',
                           description='list master config ids and assoc nodes')

@listMasterConfigs.get()
def get_listMasterConfigs(request):
    result = []
    for mconfig in DBSession.query(MasterConfiguration):
        temp = {}
        temp["id"] = mconfig.id
        temp["assoc"] = []
        for ap in mconfig.openwrt:
            temp["assoc"].append(str(ap.uuid))
        result.append(temp)
    return result

manageMasterConfig = Service(name='ManageMasterConfig',
                             path='/masterConfig/{ID}',
                             description='manage given MasterConig')

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
                           description='print given MasterConig as json')

@masterConfigJSON.get()
def getMasterConfigJSON(request):
    id = request.matchdict['ID']
    masterconf = DBSession.query(MasterConfiguration).get(id)
    if not masterconf:
        return False
    return masterconf.exportJSON()

queryMasterConfig = Service(name='QueryMasterConfig',
                            path='/masterConfig/{ID}/query',
                            description='get an option key of a masterConfig')

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

# TODO: add validator
@queryMasterConfig.post()
def post_queryMasterConfig(request):
    query = json.loads(request.body.decode())

    mconfID = request.matchdict['ID']
    masterConfig = DBSession.query(MasterConfiguration).get(mconfID)

    option = query['option']

    configs = masterConfig.configurations

    filterConfigsByPackage = []
    if 'package' in query.keys():
        package = query['package']
        for config in configs:
            if config.package == package:
                filterConfigsByPackage.append(config)
        configs = filterConfigsByPackage

    filterConfigsByName = []
    if 'name' in query.keys():
        name = query['name']
        for config in configs:
            if config.name == name:
                filterConfigsByName.append(config)
        configs = filterConfigsByName

    filterConfigsByType = []
    if 'type' in query.keys():
        type = query['type']
        for config in configs:
            configData = json.loads(config.data)
            if configData['.type'] == type:
                filterConfigsByType.append(config)
        configs = filterConfigsByType

    filterConfigsByMatchOptions = []
    if 'matchOptions' in query.keys():
        matchOptions = query['matchOptions']

        for config in configs:
            doesMatch = False

            for key, value in  matchOptions.items():
                try:
                    curConf, option = getCurConfigAndOption(config, key)
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
                filterConfigsByMatchOptions.append(config)
        configs = filterConfigsByMatchOptions

    if 'option' in query.keys():
        options = query['option']
    else:
        options = False

    result = {'values' : [],
              'added' : [],
              'deleted' : []}

    for config in configs:
        if options:
            curConf, option = getCurConfigAndOption(config, options)
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

        if 'add_options' in query.keys():
            for k, v in query['add_options'].items():
                curConfData[k] = v
                result['added'].append({k:v})

        if 'del_options' in query.keys():
            for opt in query['del_options']:
                try:
                    result['deleted'].append({opt:curConfData.pop(opt)})
                except KeyError:
                    pass

        if 'del_options' in query.keys() or \
           'add_options' in query.keys() or \
           'set' in query.keys():
            curConf.data = json.dumps(curConfData)

    return result

def getCurConfigAndOption(config, options):
    curConf = config
    optionList = options.split('.')
    option = optionList[-1]
    # TODO: handle multiple links?
    for i in range(len(optionList)-1):
        curConf = curConf.getLinkByName(optionList[i]).to_config[0]
    return curConf, option

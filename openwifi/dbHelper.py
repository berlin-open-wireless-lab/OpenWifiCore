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

def user_is_not_allowed_to_user_master_config(request, masterconf):
    from openwifi.authentication import get_nodes
    nodes = get_nodes(request)

    if all(ow in nodes for ow in masterconf.openwrt):
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
                           description='list master config ids and assoc nodes',
                           permission='view')

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

# assumes that the user has access for all nodes assinged to the master config
# (this is checked by vildate_masterconfig
def validate_masterconfig_query(request, **kwargs):
    from openwifi.authentication import get_access_list

    request.configs_were_removed = False

    accesses = get_access_list(request)
    if not accesses:
        request.error.add('', 'access denied', 'no access lists have been found for user/apikey')
        request.errors.status = 403
        return

    nodes_using_master_conf = request.masterConfig.openwrt
    accesses_for_this_mconf = filter(lambda a: any(n in nodes_using_master_conf for n in a.nodes) or a.access_all_nodes, accesses)

    composed_access = find_most_strict_access_rule(accesses_for_this_mconf)

    query = request.json_body
    queries = get_querys_of_access(composed_access)

    if set(query.items()) in [set(q.items()) for q in queries]:
        return

    pathes = get_access_pathes_with_rights(composed_access)

    configs = request.masterConfig.configurations
    configs = filter_configs(configs, query)

    still_accessible_configs = configs.copy()
    
    for config in configs:
        # TODO: find the config that shall actually be accessed
        # TODO: add possibility to nail it down to conf parameter
        config_path = config_to_path(config)
        found_match = False
        for path, rights in pathes.items():
            if pathes_are_equal_or_superset(path, config_path, regex=True):
                found_match = True
                break
        if (not found_match) or \
           (found_match and \
               (rights == 'none' or \
               (rights == 'ro' and 'set' in query))):
            request.configs_were_removed = True
            still_accessible_configs.remove(config)

    if configs and (not still_accessible_configs):
        request.errors.add('', 'access denied', 'no access to any of the matching configs')
        request.errors.status = 403

    request.still_accessible_configs = still_accessible_configs

# find the most strict access rule of a given set of rules
# deny access if there are non overlapping access rules
def find_most_strict_access_rule(accesses):
    overlapping_pathes = {}
    querys = []

    for access in accesses:
        data = json.loads(access.data)

        if access_contains_query(data):
            querys = get_access_type_query(data)
            overlapping_pathes = None
            continue

        if overlapping_pathes == None:
            querys.extend(get_access_type_query(data))
            continue

        if overlapping_pathes == {}:
            pathes = get_access_pathes_with_rights(data)
            overlapping_pathes.update(pathes)
        else:
            # find max overlapping pathes
            pathes = get_access_pathes_with_rights(data)
            forward_matches = get_matching_pathes(overlapping_pathes, pathes)
            backward_matches = get_matching_pathes(pathes, overlapping_pathes)

            # if no common pathes -> pathes will be empty
            if not (forward_matches and backward_matches):
                overlapping_pathes = None
                continue

            # if just some match -> add deeper path with lowest rights (rw > ro > none)
            # except for none add just the  path with none

            overlapping_pathes = {}
            add_pathes_from_matches(forward_matches, overlapping_pathes)
            add_pathes_from_matches(backward_matches, overlapping_pathes)

    result = querys
    result.extend(pathdict_to_access(overlapping_pathes))

    return result

def add_pathes_from_matches(matches, overlapping_pathes):
    for path, match in matches.items():
        superpath = match['superset'][0]
        superrights = match['superset'][1]
        rights = match['rights']

        # we want to get the deepest path in both directions (forward, backward)
        if superpath in overlapping_pathes:
            overlapping_pathes.pop(superpath)

        if rights == 'none' and rights == superrights:
            overlapping_pathes[path] = 'none'
            overlapping_pathes[superpath] = 'none'
        elif rights == 'none':
            overlapping_pathes[path] = 'none'
        elif superrights == 'none':
            overlapping_pathes[superpath] = 'none'
        else:
            overlapping_pathes[path] = get_lowest_rights(superrights, rights)

def access_contains_query(access_data):
    for ad in access_data:
        if ad['type'] != "query":
            return False
    return True

def get_querys_of_access(access_data):
    queries = []
    for ad in access_data:
        if ad['type'] == 'query':
            queries.append(ad['query'])
    return queries

def get_access_type_query(access_data):
    queries = []
    for ad in access_data:
        if ad['type'] == 'query':
            queries.append(ad)
    return queries

def get_access_pathes_with_rights(access_data):
    """ returns pathes of access data as a dict
        with the path as key and the rights as 
        value """
    pathes = {}
    for ad in access_data:
        if ad['type'] == 'pathstring':
            pathes[ad['string']] = ad['access']
    return pathes

def get_lowest_rights(rights1, rights2):
    right_order = {'rw': 3, 'ro': 2, 'none': 1}
    if right_order[rights1] > right_order[rights2]:
        return rights2
    else:
        return rights1

def get_matching_pathes(pathlist1, pathlist2):
    match = {}

    for path1 in pathlist1:
        for path2 in pathlist2:
            if pathes_are_equal_or_superset(path1, path2):
                match[path2] = {"rights": pathlist2[path2], 
                                "superset": (path1, pathlist1[path1])}
    return match

def pathes_are_equal_or_superset(ref_path, comp_path, regex=False):
    """
    assumes that first path is the reference path and 
    """
    ref_path_split = split_path(ref_path)
    comp_path_split = split_path(comp_path)

    if len(ref_path_split) > len(comp_path_split):
        return False

    i = 0
    # TODO: use greenery (https://github.com/qntm/greenery) for comparing
    for part in ref_path_split:
        if regex:
            import re
            if not re.match(part, comp_path_split[i]):
                return False
        else:
            if part != comp_path_split[i]:
                return False
        i += 1

    return True

def split_path(path):
    split =  path.split(').')
    for i in range(len(split)-1):
        split[i] += ')'
    return split

def pathdict_to_access(pathdict):
    result = []
    if not pathdict:
        return result

    for path, rights in pathdict.items():
        new_access = {}
        new_access['type'] = 'pathstring'
        new_access['string'] = path
        new_access['access'] = rights
        result.append(new_access)

    return result

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
                            validators=(validate_masterconfig,validate_masterconfig_query),
                            permission='view')

@queryMasterConfig.get()
def get_queryMasterConfig(request):
    usage = {'package' : 'optional package name',
             'name'    : 'optional config name',
             'type'    : 'optional config type',
             'matchOptions' : 'optional dict of option-value pairs to match, dot is possible like in option, use null if you just want to check of the option exists',
             'option'  : 'optional option name, it is possible to go though a link with dots like: linkname.option',
             'set'     : 'optional set option to this value',
             'add_config' : 'add config, type and package are mandatory for new configs, use either "new" for a new config, "new-nonexistent" to just create if no other exists, or a node-id to add a config',
             'add_options' : 'optional dict of key-value pairs that should be added to found configs',
             'del_options' : 'optional list of options to remove'}
    return usage

@queryMasterConfig.post()
def post_queryMasterConfig(request):
    query = request.json_body

    if request.configs_were_removed:
        result = query_master_config(query, request.masterConfig, 
                                     configs = request.still_accessible_configs)
        result['info'] = 'configs were removed'
        return result
    else:
        return query_master_config(query, request.masterConfig)

def query_master_config(query, master_config, configs=None):
    if configs ==  None:
        configs = master_config.configurations
        configs = filter_configs(configs, query)

    if 'option' in query:
        options = query['option']
    else:
        options = False

    result = {'values' : [],
              'added' : [],
              'deleted' : [],
              'matched_configs' : ['c'+str(config.id) for config in configs]}

    if 'add_config' in query and (query['add_config'] == 'new' or \
            (query['add_config'] == 'new-nonexistent' and not configs)):
        new_config = Configuration(getMaxId(Configuration))
        new_config.package = query['package']
        if 'name' in query:
            new_config.name = query['name']
        else:
            new_config.name = ''
        new_data = {'.type' : query['type'],
                    '.anonymous' : 'name' not in query,
                    '.name' : new_config.name,
                    '.index' : master_config.get_max_index_of_package(query['package'])+1}
        new_config.data = json.dumps(new_data)
        master_config.configurations.append(new_config)
        result['new_config'] = 'c'+str(new_config.id)
        if configs:
            configs.append(new_config)
        else:
            configs = [new_config]
    elif 'add_config' in query and (query['add_config'] not in ['new', 'new-nonexistent']):
        if query['add_config'][0] == 'c':
            id = int(query['add_config'][1:])
            config = DBSession.query(Configuration).get(id)
            master_config.configurations.append(config)
            result['new_config'] = 'c'+str(new_config.id)
            if configs:
                configs.append(new_config)
            else:
                configs = [new_config]

    for config in configs:
        if options:
            curConf, option = follow_options_path(config, options)
            curConfData = json.loads(curConf.data)
            try:
                value = curConfData[option]
            except KeyError:
                value = None

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
        path += "." + config.from_links[0].data + ' (OPENWIFI_LINK)'
        config = config.from_links[0].from_config[0]
        path += "." + config.name + ' (' + config.get_type() + ')'

    return path[1:]

def validate_config_node_access(request, **kwargs):
    node = request.matchdict['NODE']
    result = get_config_node(node, request)

    if not result:
        request.errors.add('querystring', 'not found', "couldn't find a matching node")

    request.nodeData = result

def validate_config_node_link_access(request, **kwargs):
    from_node = request.matchdict['FROM_NODE']
    to_node = request.matchdict['TO_NODE']
    from_node = get_config_node(from_node, request)
    to_node = get_config_node(to_node, request)

    if not from_node or not to_node:
        request.errors.add('querystring', 'not found', "couldn't find a matching node")
        return

    if not 'conf' in to_node or not 'conf' in from_node:
        request.errors.add('querystring', 'node must be config', "bothe nodes muste be config nodes")
        return

    request.from_node = from_node
    request.to_node = to_node

def get_config_node(node, request):
    if node[0] == 'l':
        link = DBSession.query(ConfigurationLink).get(node[1:])
        if user_is_not_allowed_to_user_master_config(request, link.masterconf):
            request.errors.add('', 'access denied', 'access to this master config was denied')
            request.errors.status = 403
            return

        result = {"link": link.data, "id": node}

    if node[0] == 'c':
        conf = DBSession.query(Configuration).get(node[1:])
        if user_is_not_allowed_to_user_master_config(request, conf.masterconf):
            request.errors.add('', 'access denied', 'access to this master config was denied')
            request.errors.status = 403
            return

        result = {"conf": json.loads(conf.data), "id": node, "path": config_to_path(conf)}

    return result

masterConfNodeInfo = Service(name='MasterConfNodeInfo',
                             path='/masterConfig/Node/{NODE}',
                             description='get node data',
                             validators=(validate_config_node_access,))

@masterConfNodeInfo.get()
def get_master_conf_node_info(request):
    return request.nodeData

masterConfNodeLink = Service(name='MasterConfNodeLink',
                             path='/masterConfig/Node/{FROM_NODE}/link/{TO_NODE}',
                             description='create a link between configs',
                             validators=(validate_config_node_link_access,))

@masterConfNodeLink.get()
def get_master_conf_node_link(request):
    return "add link data as post data"

@masterConfNodeLink.post()
def post_master_conf_node_link(request):
    data = request.body.decode()
    from_id = int(request.from_node['id'][1:])
    to_id = int(request.to_node['id'][1:])

    from_config = DBSession.query(Configuration).get(from_id)
    to_config = DBSession.query(Configuration).get(to_id)

    new_link = ConfigurationLink(getMaxId(ConfigurationLink))
    new_link.data = data
    new_link.to_config.append(to_config)
    new_link.from_config.append(from_config)
    new_link.masterconf = from_config.masterconf
    
    DBSession.add(new_link)

@masterConfNodeLink.delete()
def delete_master_conf_node_link(request):
    from_id = int(request.from_node['id'][1:])
    to_id = int(request.to_node['id'][1:])

    from_config = DBSession.query(Configuration).get(from_id)
    to_config = DBSession.query(Configuration).get(to_id)

    to_be_deleted = []

    for link in from_config.to_links:
        if to_config in link.to_config:
            to_be_deleted.append(link)

    for link in to_be_deleted:
        DBSession.delete(link)

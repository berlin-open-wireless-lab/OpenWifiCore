from celery import Celery, signature
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from openwifi.jobserver_config import sqlurl, brokerurl, redishost, redisport, redisdb
from openwifi.netcli import jsonubus
from openwifi.models import ( OpenWrt, Templates, ConfigArchive )
from pyuci import Uci, Package, Config
from openwifi.utils import id_generator

import datetime
import redis
import json

from pkg_resources import iter_entry_points

from openwifi import registerDatabaseListeners

from celery.signals import celeryd_after_setup

from openwifi.utils import diffChanged

@celeryd_after_setup.connect
def setup_register_database_listeners(sender, instance, **kwargs):
    registerDatabaseListeners({})

app = Celery('tasks', backend="redis://"+redishost, broker=brokerurl)

app.conf.CELERYBEAT_SCHEDULE = {
    'look-for-unconfigured-nodes-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_unconfigured_nodes',
        'schedule': datetime.timedelta(seconds=30),
        'args': ()
    },
    'update-node-status-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_status',
        'schedule': datetime.timedelta(seconds=30),
        'args': ()
    },
    'update-capabilities-and-config-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_capabilities_and_config',
        'schedule': datetime.timedelta(seconds=30),
        'args': ()
    },
}

app.conf.CELERY_TIMEZONE = 'UTC'
app.conf.CELERY_TASK_RESULT_EXPIRES = datetime.timedelta(hours=1)

# Add Plugin Tasks
for entry_point in iter_entry_points(group='OpenWifi.plugin', name="addJobserverTasks"):
    entry_function = entry_point.load()
    entry_function(app)

def get_sql_session():
    engine = create_engine(sqlurl)
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    return Session()

def get_jsonubus_from_uuid(uuid):
    DBSession=get_sql_session()
    device = DBSession.query(OpenWrt).get(uuid)
    js = get_jsonubus_from_openwrt(device)
    DBSession.close()
    return js

def get_jsonubus_from_openwrt(openwrt):
    if openwrt.communication_protocol == "JSONUBUS_HTTPS":
        device_url = "https://"+openwrt.address+"/ubus"
    else:
        device_url = "http://"+openwrt.address+"/ubus"

    js = jsonubus.JsonUbus(url = device_url, \
                           user = openwrt.login, \
                           password = openwrt.password)
    return js

def return_jsonconfig_from_device(openwrt):
    js = get_jsonubus_from_openwrt(openwrt)
    device_configs = js.call('uci', 'configs')
    configuration="{"
    for cur_config in device_configs[1]['configs']:
        configuration+='"'+cur_config+'":'+json.dumps(js.call("uci","get",config=cur_config)[1])+","
    configuration = configuration[:-1]+"}"
    return configuration

@app.task
def get_config(uuid):
    try:
        DBSession = get_sql_session()
        device = DBSession.query(OpenWrt).get(uuid)

        if device.configured:
            newConf = return_jsonconfig_from_device(device)

            newUci = Uci()
            newUci.load_tree(newConf)

            oldUci = Uci()
            oldUci.load_tree(device.configuration)

            diff = oldUci.diff(newUci)

            if diffChanged(diff):
                device.append_diff(diff, DBSession, "download: ")
                device.configuration = newConf
        else:
            device.configuration = return_jsonconfig_from_device(device)
            device.configured = True

        DBSession.commit()
        DBSession.close()
        return True
    except Exception as thrownexpt:
        print(thrownexpt)
        device.configured = False
        DBSession.commit()
        DBSession.close()
        return False

@app.task
def archive_config(uuid):
    DBSession = get_sql_session()
    device = DBSession.query(OpenWrt).get(uuid)

    if not device:
        return False

    confToBeArchived = ConfigArchive(datetime.datetime.now(), \
                                     device.configuration, \
                                     device.uuid, \
                                     id_generator())
    DBSession.add(confToBeArchived)
    DBSession.commit()
    DBSession.close()

    return True

@app.task
def diff_update_config(diff, uuid):
    js = get_jsonubus_from_uuid(uuid)
    # add new packages via file-interface and insert corresponding configs
    for packname, pack in diff['newpackages'].items():
        js.call('file', 'write', path='/etc/config/'+packname, data='')
        for confname, conf in pack.items():
            js.call('uci','add',config=packname, **conf.export_dict(foradd=True))
            js.call('uci','commit',config=packname)

    # add new configs
    for confname, conf in diff['newconfigs'].items():
        js.call('uci','add',config=confname[0], **conf.export_dict(foradd=True))
        js.call('uci','commit', config=confname[0])

    # remove old configs
    for confname, conf in diff['oldconfigs'].items():
        js.call('uci','delete',config=confname[0],section=confname[1])
        js.call('uci','commit',config=confname[0])

    # remove old packages via file-interface
    for packname, pack in diff['oldpackages'].items():
        js.call('file', 'exec', command='/bin/rm',
                params=['/etc/config/'+packname])

    # add new options
    for optkey, optval in diff['newOptions'].items():
        js.call('uci','set',config=optkey[0],section=optkey[1],
                values={optkey[2]:optval})
        js.call('uci','commit',config=optkey[0])

    # delete old options
    for optkey in diff['oldOptions'].keys():
        js.call('uci','delete',config=optkey[0],section=optkey[1],
                option=optkey[2])
        js.call('uci','commit',config=optkey[0])

    # set changed options
    for optkey, optval in diff['chaOptions'].items():
        js.call('uci','set',config=optkey[0],section=optkey[1],
                values={optkey[2]:optval[1]})
        js.call('uci','commit',config=optkey[0])

@app.task(bind=True)
def update_config(self, uuid):
    try:
        DBSession = get_sql_session()
        device = DBSession.query(OpenWrt).get(uuid)
        new_configuration = Uci()
        new_configuration.load_tree(device.configuration)

        cur_configuration = Uci()
        cur_configuration.load_tree(return_jsonconfig_from_device(device))
        conf_diff = cur_configuration.diff(new_configuration)
        changed = diffChanged(conf_diff)

        if changed:
            diff_update_config(conf_diff, uuid)
    except Exception as exc:
        DBSession.commit()
        DBSession.close()
        raise self.retry(exc=exc, countdown=60)
    
    if changed:
        device.append_diff(conf_diff, DBSession, "upload: ")
    DBSession.commit()
    DBSession.close()

@app.task
def update_unconfigured_nodes():
    DBSession = get_sql_session()
    devices = DBSession.query(OpenWrt).filter(OpenWrt.configured==False)
    for device in devices:
        arguments = ( device.uuid, )
        update_device_task = signature('openwifi.jobserver.tasks.get_config',args=arguments)
        update_device_task.delay()

@app.task
def update_status():
    DBSession = get_sql_session()
    devices = DBSession.query(OpenWrt)
    redisDB = redis.StrictRedis(host=redishost, port=redisport, db=redisdb)
    for device in devices:
        js = get_jsonubus_from_openwrt(device)
        try:
            networkstatus = js.callp('network.interface','dump')
        except OSError as error:
            redisDB.hset(str(device.uuid), 'status', "{message} ({errorno})".format(message=error.strerror, errorno=error.errno))
        except:
            redisDB.hset(str(device.uuid), 'status', "error receiving status...")
        else:
            redisDB.hset(str(device.uuid), 'status', "online")
            redisDB.hset(str(device.uuid), 'networkstatus', json.dumps(networkstatus['interface']))

class MetaconfWrongFormat(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def update_template(openwrtConfJSON, templateJSON):
    openwrt_config = Uci()
    openwrt_config.load_tree(openwrtConfJSON)
    metaconf = json.loads(templateJSON)['metaconf']
    for package in metaconf['change']['add']: # packages to be added
        if  package not in openwrt_config.packages.keys():
            openwrt_config.add_package(package)
    for package in metaconf['change']['del']: # packages to be deleted
        if package in openwrt_config.packages.keys():
            openwrt_config.packages.pop(package)
    packages = metaconf['packages']
    for package_match in packages:
        if not package_match['type']=='package':
            raise MetaconfWrongFormat('first level should be type: \
                     package, but found: '+ cur_package_match['type']) 
        package = package_match['matchvalue']
        # scan for packages to be added and add
        for config in package_match['change']['add']:
            nameMismatch = True
            typeMismatch = True
            # match names
            if config[0] in openwrt_config.packages[package].keys():
                nameMismatch = False
            # match types
            for confname, conf in openwrt_config.packages[package].items():
                if conf.uci_type == config[1]:
                    typeMismatch = False
                    break
            if (config[2] == 'always') or\
               (config[2] == 'typeMismatch' and typeMismatch) or\
               (config[2] == 'nameMismatch' and nameMismatch) or\
               (config[2] == 'bothMismatch' and typeMismatch and nameMismatch):
                openwrt_config.packages[package][config[0]] = Config(config[1],config[0],config[0]=='') #Config(ucitype, name, anon)
        # scan for packages to be removed and delete
        for config in package_match['change']['del']:
            confmatch = config[2]
            # match names
            if config[0] in openwrt_config.packages[package].keys():
                if confmatch == 'always'  or confmatch == 'nameMatch':
                    openwrt_config.packages[package].pop(config[0])
            # match types
            for confname, conf in openwrt_config.packages[package].items():
                if conf.uci_type == config[1]:
                    if confmatch == 'always' or confmatch == 'typeMatch':
                        openwrt_config.packages[package].pop(confname)
                    if confmatch == 'bothMatch' and confname == conf[0]:
                        openwrt_config.packages[package].pop(confname)
        # go into config matches
        for conf_match in  package_match['config']:
            matched_configs = []
            configs_to_be_matched = list(openwrt_config.packages[package].values())
            while conf_match!='' and configs_to_be_matched:
                for config in configs_to_be_matched:
                    if conf_match['matchtype']=='name':
                        if config.name==conf_match['matchvalue']:
                            matched_configs.append(config)
                    if conf_match['matchtype']=='type':
                        if config.uci_type==conf_match['ucitype']:
                            matched_configs.append(config)
                for mconfig in matched_configs:
                    for option in conf_match['change']['add']:
                        mconfig.keys[option[0]] = option[1]
                    for option in conf_match['change']['del']:
                        try:
                            mconfig.keys.pop(option)
                        except KeyError:
                            pass
                    # new options that might not be in older templates
                    try:
                        for option in conf_match['change']['appendToList']:
                            if type(mconfig.keys[option[0]]) is list and option[1] not in mconfig.keys[option[0]]:
                                mconfig.keys[option[0]].append(option[1])
                        for option in conf_match['change']['removeFromList']:
                            if type(mconfig.keys[option[0]]) is list and option[1]  in mconfig.keys[option[0]]:
                                indexInList = mconfig.keys[option[0]].index(option[1])
                                mconfig.keys[option[0]].pop(indexInList)
                    except KeyError:
                        pass
                configs_to_be_matched=matched_configs
                conf_match=conf_match['next']
    return openwrt_config
        
@app.task
def update_template_config(id):
        DBSession = get_sql_session()
        template = DBSession.query(Templates).get(id)
        for openwrt in template.openwrt:
            newconf = update_template(openwrt.configuration, template.metaconf)
            openwrt.configuration = newconf.export_json()
        DBSession.commit()
        for openwrt in template.openwrt:
            updateconf = signature('openwifi.jobserver.tasks.update_config',
                                 args=(openwrt.uuid,))
            updateconf.delay()
        DBSession.close()

@app.task
def update_openwrt_sshkeys(uuid):
    DBSession = get_sql_session()
    openwrt = DBSession.query(OpenWrt).get(uuid)
    keys = ""
    for sshkey in openwrt.ssh_keys:
        keys = keys+'#'+sshkey.comment+'\n'
        keys = keys+sshkey.key+'\n'
    js = get_jsonubus_from_openwrt(openwrt)
    keyfile='/etc/dropbear/authorized_keys'
    js.call('file', 'write', path=keyfile, data=keys)
    js.call('file', 'exec',command='chmod', params=['600',keyfile])
    DBSession.close()

@app.task
def exec_on_device(uuid, cmd, prms):
    DBSession = get_sql_session()
    openwrt = DBSession.query(OpenWrt).get(uuid)

    if not openwrt:
        return False

    js = get_jsonubus_from_openwrt(openwrt)
    ans = js.call('file', 'exec', command=cmd, params=prms)
    DBSession.close()

    return ans

@app.task
def update_capabilities_and_config():
    update_capabilities()
    update_services_config_on_node()

@app.task
def update_capabilities():
    DBSession = get_sql_session()
    from openwifi.models import Service

    services = DBSession.query(Service)
    devices = DBSession.query(OpenWrt)

    for service in services:
        for device in devices:
            uuid = device.uuid
            cmd = 'sh'
            args = ['-c', service.capability_script]

            ans = exec_on_device(uuid, cmd, args)
            stdout = ans[1]['stdout']

            if stdout == service.capability_match:
                device.add_capability(service.name)
                DBSession.commit()

@app.task
def update_services_config_on_node():
    DBSession = get_sql_session()
    devices = DBSession.query(OpenWrt)
    from openwifi.models import Service

    for device in devices:
        capabilities = json.loads(device.capabilities)
        for capability in device.get_capabilities():
            assoc_service = DBSession.query(Service).filter(Service.name == capability).first()
            if assoc_service:
                update_service_config_on_node(assoc_service, device)
                DBSession.commit()

def update_service_config_on_node(service, node):
    master_config = node.masterconf

    from openwifi.dbHelper import query_master_config
    for query in service.get_queries():
        query_master_config(query, master_config)

def get_wifi_devices_via_jsonubus(js):
    wifi_devices = js.call('iwinfo', 'devices')
    return wifi_devices

def get_assoclist_via_jsonubus_of_wifi_device(js, wifi_device):
    assoclist = js.call('iwinfo', 'assoclist', device=wifi_device)
    return assoclist

def get_assoc_count_of_wifi_device(js, wifi_device):
    assoclist = get_assoclist_via_jsonubus_of_wifi_device(js, wifi_device)
    assoclist_results = assoclist[1]['results']
    return len(assoclist_results)

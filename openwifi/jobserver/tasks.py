from celery import Celery, signature
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openwifi.jobserver_config import sqlurl, brokerurl, redishost, redisport, redisdb
from openwifi.netcli import jsonubus
from openwifi.models import ( OpenWrt, Templates )
from pyuci import Uci, Package, Config
from datetime import timedelta
import redis
import json

app = Celery('tasks', broker=brokerurl)

app.conf.CELERYBEAT_SCHEDULE = {
    'look-for-unconfigured-nodes-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_unconfigured_nodes',
        'schedule': timedelta(seconds=30),
        'args': ()
    },
    'update-node-status-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_status',
        'schedule': timedelta(seconds=30),
        'args': ()
    },

}

app.conf.CELERY_TIMEZONE = 'UTC'

def get_sql_session():
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession=Session()
    return DBSession

def return_config_from_node_as_json(url, user, passwd):
        js = jsonubus.JsonUbus(url = url, user = user, password = passwd)
        device_configs = js.call('uci', 'configs')
        configuration="{"
        for cur_config in device_configs[1]['configs']:
            configuration+='"'+cur_config+'":'+json.dumps(js.call("uci","get",config=cur_config)[1])+","
        configuration = configuration[:-1]+"}"
        return configuration

@app.task
def get_config(uuid):
    try:
        DBSession=get_sql_session()
        device = DBSession.query(OpenWrt).get(uuid)
        device_url = "http://"+device.address+"/ubus"
        device.configuration = return_config_from_node_as_json(device_url,
                                                               device.login,
                                                               device.password)
        device.configured = True
        DBSession.commit()
        DBSession.close()
        return True
    except Exception as thrownexpt:
        print(thrownexpt)
        device.configured = False
        return False


@app.task
def diff_update_config(diff, url, user, passwd):
    js = jsonubus.JsonUbus(url=url,
                           user=user,
                           password=passwd)
    # add new packages via file-interface and insert corresponding configs
    for packname, pack in diff['newpackages'].items():
        js.call('file', 'write', path='/etc/config/'+packname, data='')
        for confname, conf in pack.items():
            js.call('uci','add',config=packname, **conf.export_dict(foradd=True))
            js.call('uci','commit',config=packname)

    # add new configs
    for confname, conf in diff['newconfigs']:
        js.call('uci','add',config=confname[0], **conf.export_dict(foradd=True))
        js.call('uci','commit', config=confname[0])

    # remove old configs
    for confname, conf in diff['oldconfigs']:
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

@app.task
def update_config(uuid):
    DBSession = get_sql_session()
    device = DBSession.query(OpenWrt).get(uuid)
    new_configuration = Uci()
    new_configuration.load_tree(device.configuration)
    device_url = "http://"+device.address+"/ubus"
    cur_configuration = Uci()
    cur_configuration.load_tree(return_config_from_node_as_json(device_url,
                                                                device.login,
                                                                device.password))
    conf_diff = cur_configuration.diff(new_configuration)
    update_diff_conf = signature('openwifi.jobserver.tasks.diff_update_config',
                                 args=(conf_diff, device_url,
                                       device.login, device.password))
    DBSession.commit()
    DBSession.close()
    update_diff_conf.delay()

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
        device_url = "http://"+device.address+"/ubus"
        js = jsonubus.JsonUbus(url=device_url, user=device.login, password=device.password)
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
    url = "http://"+openwrt.address+"/ubus"
    js = jsonubus.JsonUbus(url=url,
                           user=openwrt.login,
                           password=openwrt.password)
    js.call('file', 'write', path='/etc/dropbear/authorized_keys', data=keys)
    DBSession.close()

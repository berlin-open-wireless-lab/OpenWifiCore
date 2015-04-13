from celery import Celery, signature
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openwifi.jobserver_config import sqlurl, brokerurl, redishost, redisport, redisdb
from openwifi.netcli import jsonubus
from openwifi.models import ( OpenWrt )
from pyuci import Uci
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

def return_config_from_node_as_json(url, user, passwd):
        js = jsonubus.JsonUbus(url = url, user = user, password = passwd)
        device_configs = js.call('uci', 'configs')
        configuration="{"
        for cur_config in device_configs[1]['configs']:
            configuration+='"'+cur_config+'":'+str(js.call("uci","get",config=cur_config)[1])+","
        configuration = configuration[:-1]+"}"
        configuration = configuration.replace("True", "'true'")
        configuration = configuration.replace("False", "'false'")
        configuration = configuration.replace("'",'"')
        return configuration

@app.task
def get_config(uuid):
    try:
        engine = create_engine(sqlurl)
        Session = sessionmaker()
        Session.configure(bind=engine)
        DBSession=Session()
        device = DBSession.query(OpenWrt).get(uuid)
        device_url = "http://"+device.address+"/ubus"
        device.configuration = return_config_from_node_as_json(device_url,
                                                               device.login,
                                                               device.password)
        device.configured = True
        DBSession.commit()
        DBSession.close()
        return True
    except:
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
                values={optkey[3]:optval})
        js.call('uci','commit',config=optkey[0])

    # delete old options
    for optkey in diff['oldOptions'].keys():
        js.call('uci','delete',config=optkey[0],section=optkey[1],
                option=optkey[2])
        js.call('uci','commit',config=optkey[0])

    # set changed options
    for optkey, optval in diff['chaOptions'].items():
        js.call('uci','set',config=optkey[0],section=optkey[1],
                values={optkey[3]:optval[1]})
        js.call('uci','commit',config=optkey[0])

@app.task
def update_config(uuid):
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession = Session()
    device = DBSession.query(OpenWrt).get(uuid)
    new_configuration = Uci()
    new_configuration.load_tree(device.configuration)
    device_url = "http://"+device.address+"/ubus"
    cur_configuration = Uci()
    cur_configuration.load_tree(return_config_from_node_as_json(device_url,
                                                                device.login,
                                                                device.password))
    conf_diff = cur_configuration.diff(new_configuration)
    DBSession.commit()
    DBSession.close()
    update_diff_conf = signature('openwifi.jobserver.tasks.diff_update_config',
                                 args=(conf_diff, device_url,
                                       device.login, device.password))
    update_diff_conf.delay()

@app.task
def update_unconfigured_nodes():
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession = Session()
    devices = DBSession.query(OpenWrt).filter(OpenWrt.configured==False)
    for device in devices:
        arguments = ( device.uuid, )
        update_device_task = signature('openwifi.jobserver.tasks.get_config',args=arguments)
        update_device_task.delay()

@app.task
def update_status():
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession = Session()
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



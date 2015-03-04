from celery import Celery, signature
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openwifi.jobserver_config import sqlurl, brokerurl, redishost, redisport, redisdb
from openwifi.netcli import jsonubus
from openwifi.models import ( OpenWrt )
from openwifi.jobserver.uci import Uci
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
        return False

@app.task
def update_config(uuid):
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession = Session()
    device = DBSession.query(OpenWrt).get(uuid)
    configuration = Uci()
    configuration.load_tree(device.configuration)
    device_url = "http://"+device.address+"/ubus"
    js = jsonubus.JsonUbus(url=device_url, user=device.login, password=device.password)
    DBSession.commit()
    DBSession.close()
    for package, content in configuration.packages.items():
        if package == config:
            for confname, conf in content.items():
                confdict=conf.export_dict()
                confdict['values'].pop(".index")
                js.call('uci', 'set', config=package, **conf.export_dict())
                js.call('uci', 'commit', config=package)
    return True

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



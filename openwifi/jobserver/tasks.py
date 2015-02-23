from celery import Celery, signature
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openwifi.jobserver_config import sqlurl, brokerurl
from openwifi.netcli import jsonubus
from openwifi.models import ( OpenWrt )
from openwifi.jobserver.uci import Uci
from datetime import timedelta

app = Celery('tasks', broker=brokerurl)

app.conf.CELERYBEAT_SCHEDULE = {
    'add-every-30-seconds': {
        'task': 'openwifi.jobserver.tasks.update_unconfigured_nodes',
        'schedule': timedelta(seconds=30),
        'args': ()
    },
}

app.conf.CELERY_TIMEZONE = 'UTC'



@app.task
def get_config(uuid):
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession=Session()
    device = DBSession.query(OpenWrt).get(uuid)
    device_url = "http://"+device.address+"/ubus"
    js = jsonubus.JsonUbus(url=device_url, user=device.login, password=device.password)
    device_configs = js.call('uci', 'configs')
    device.configuration="{"
    for cur_config in device_configs[1]['configs']:
        device.configuration+='"'+cur_config+'":'+str(js.call("uci","get",config=cur_config)[1])+","
    device.configuration=device.configuration[:-1]+"}"
    device.configuration=device.configuration.replace("True", "'true'")
    device.configuration=device.configuration.replace("False", "'false'")
    device.configuration=device.configuration.replace("'",'"')
    device.configured = True
    DBSession.commit()
    DBSession.close()
    return True
@app.task
def update_config(uuid, config):
    engine = create_engine(sqlurl)
    Session = sessionmaker()
    Session.configure(bind=engine)
    DBSession=Session()
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
    DBSession=Session()
    devices = DBSession.query(OpenWrt).filter(OpenWrt.configured==False)
    for device in devices:
        arguments=[]
        arguments.append(device.uuid)
        update_device_task = signature('openwifi.jobserver.tasks.update_config',args=arguments)
        update_device_task.delay()


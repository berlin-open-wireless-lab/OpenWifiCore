from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid_rpc.jsonrpc import jsonrpc_method
from pyramid import httpexceptions as exc
import transaction
import random
from datetime import datetime
import string
import pprint
from openwifi.jobserver_config import redishost, redisport, redisdb
import redis

import json
from pyuci import Uci
import openwifi.jobserver.tasks as jobtask

from sqlalchemy.exc import DBAPIError

from .models import (
    AccessPoint,
    DBSession,
    OpenWrt,
    ConfigArchive
    )

from .forms import (
        AccessPointAddForm,
        OpenWrtEditForm,
        )

from .utils import generate_device_uuid

@view_config(route_name='home', renderer='templates/home.jinja2', layout='base')
def home(request):
    return {}

@jsonrpc_method(method='device_register', endpoint='api')
def device_register(request, uuid, name, address, distribution, version, proto):
    ap = OpenWrt(name, address, distribution, version, uuid, False)
    DBSession.add(ap)
    DBSession.flush()

@view_config(route_name='openwrt_list', renderer='templates/openwrt.jinja2', layout='base')
def openwrt_list(request):
    openwrt = DBSession.query(OpenWrt)
    devices = []
    for device in openwrt:
        devices.append(str(device.uuid))
    return {'idfield': 'uuid',
            'domain': 'openwrt',
            'devices': json.dumps(devices),
            'confdomain': 'openwrt_edit_config',
            'items': openwrt,
            'table_fields': ['name', 'distribution', 'version', 'address', 'uuid', 'login', 'password', 'configuration', 'configured']}

@view_config(route_name='confarchive', renderer='templates/archive_list.jinja2', layout='base')
def confarchive(request):
    configs = DBSession.query(ConfigArchive)
    return {'idfield': 'id',
            'domain': 'confarchive',
            'items': configs,
            'table_fields': ['date', 'id', 'router_uuid', 'configuration'],
            'actions' : {'show config':'archive_edit_config',
                         'apply config':'archive_apply_config'}
            }

@view_config(route_name='archive_apply_config', renderer='templates/archive_apply_config.jinja2', layout='base')
def archiveapplyconfig(request):
    config = DBSession.query(ConfigArchive).get(request.matchdict['id'])
    if not config:
        return exc.HTTPNotFound()
    openwrt = DBSession.query(OpenWrt)
    devices = {}
    if request.POST:
        for name,value in request.POST.dict_of_lists().items():
            if name!='submitted' and value: # if item is not the submit button and it's checkd
                deviceToBeUpdated = DBSession.query(openwrt).get(name)
                deviceToBeUpdated.configuration = config.configuration
                transaction.commit()
                jobtask.update_config.delay(str(deviceToBeUpdated.uuid))
            return HTTPFound(location = request.route_url('confarchive'))
    for device in openwrt:
        devices[str(device.name)] = str(device.uuid)
    return { 'devices' : devices }

# @view_config(route_name='openwrt_edit', renderer='templates/openwrt_edit.jinja2', layout='base')
def openwrt_edit(request):
    form = OpenWrtEditForm(request.POST)
    ap = DBSession.query(OpenWrt).filter_by(uuid=form.uuid).one()
    if request.method == 'POST' and form.validate():
        return HTTPFound(locaton = request.route_url('openwrt_list'))

    return {'form': form}

@view_config(route_name='openwrt_detail', renderer='templates/openwrt_detail.jinja2', layout='base')
def openwrt_detail(request):
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()

    return {'device': device,
            'fields': ['name', 'distribution', 'version', 'address', 'uuid'],
            'actions': ['delete', 'getConfig', 'saveConfToArchive']}

@view_config(route_name='openwrt_edit_config', renderer='templates/openwrt_edit_config.jinja2', layout='base')
def openwrt_edit_config(request):
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()
    conf = Uci()
    conf.load_tree(device.configuration);
    if request.POST:
        configsToBeUpdated=[]
        newConfig = {}
        for key, val in request.POST.dict_of_lists().items():
            if key != "submitted":
                val[0] = val[0].replace("'", '"') # for better json recognition
                packagename, configname, optionname = key.split()
                if not (packagename in newConfig.keys()):
                    newConfig[packagename] = {}
                    newConfig[packagename]['values'] = {}
                if not (configname in newConfig[packagename]['values'].keys()):
                    newConfig[packagename]['values'][configname] = {}
                try:
                    savevalue = json.loads(val[0])
                except ValueError:
                    savevalue = val[0]
                newConfig[packagename]['values'][configname][optionname] = savevalue
        newUci = Uci()
        newUci.load_tree(json.dumps(newConfig));
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(conf.diff(newUci));
        device.configuration = newUci.export_json()
        transaction.commit()
        jobtask.update_config.delay(request.matchdict['uuid'])
        return HTTPFound(location=request.route_url('openwrt_list'))
    return{ 'hiddenOptions' : ['.index','.type','.name','.anonymous'],
            'config'        : conf,
           'devicename'     : device.name}


@view_config(route_name='archive_edit_config', renderer='templates/archive_edit_config.jinja2', layout='base')
def archive_edit_config(request):
    archiveConfig = DBSession.query(ConfigArchive).get(request.matchdict['id'])
    if not archiveConfig:
        return exc.HTTPNotFound()
    device = DBSession.query(OpenWrt).get(archiveConfig.router_uuid)
    if not device:
        return exc.HTTPNotFound()
    conf = Uci()
    conf.load_tree(archiveConfig.configuration);
    if request.POST:
        configsToBeUpdated=[]
        newConfig = {}
        for key, val in request.POST.dict_of_lists().items():
            if key != "submitted":
                val[0] = val[0].replace("'", '"') # for better json recognition
                packagename, configname, optionname = key.split()
                if not (packagename in newConfig.keys()):
                    newConfig[packagename] = {}
                    newConfig[packagename]['values'] = {}
                if not (configname in newConfig[packagename]['values'].keys()):
                    newConfig[packagename]['values'][configname] = {}
                try:
                    savevalue = json.loads(val[0])
                except ValueError:
                    savevalue = val[0]
                newConfig[packagename]['values'][configname][optionname] = savevalue
        confToBeArchivedNew = ConfigArchive(datetime.now(),
                                            json.dumps(newConfig),
                                            archiveConfig.router_uuid,
                                            id_generator())
        DBSession.add(confToBeArchivedNew)
        return HTTPFound(location=request.route_url('confarchive'))
    return{ 'hiddenOptions' : ['.index','.type','.name','.anonymous'],
            'config'        : conf,
            'routerName'    : device.name,
            'date'          : archiveConfig.date}



@view_config(route_name='openwrt_add', renderer='templates/openwrt_add.jinja2', layout='base')
def openwrt_add(request):
    form = OpenWrtEditForm(request.POST)
    if request.method == 'POST' and form.validate():
        ap = OpenWrt(form.name.data, form.address.data, form.distribution.data, form.version.data, form.uuid.data, form.login.data, form.password.data, False)
        DBSession.add(ap)
        return HTTPFound(location=request.route_url('openwrt_list'))

    save_url = request.route_url('openwrt_add')
    return {'save_url':save_url, 'form':form}

@view_config(route_name='templates', renderer='templates/templates.jinja2', layout='base')
def templates(request):
    return {}

@view_config(route_name='templates_add', renderer='templates/templates_add.jinja2', layout='base')
def templates_add(request):
    if request.POST:
        # init metaconf
        metaconf = {}
        metaconf['metaconf'] = {}
        metaconf['metaconf']['change']= {}
        metaconf['metaconf']['change']['add']= []
        metaconf['metaconf']['change']['del']= []
        metaconf['metaconf']['packages']= []

        # dictonary to store data from form
        formdata = {}
        # first read all values into formdata
        for key, val in request.POST.dict_of_lists().items():
            keysplit = key.split('.')
            curlevel=formdata
            i=1
            for splittedkey in keysplit:
                if(i<len(keysplit)):
                    try:
                        curlevel=curlevel[splittedkey]
                    except KeyError:
                        curlevel[splittedkey]={}
                        curlevel=curlevel[splittedkey]
                else:
                    curlevel[splittedkey]=val[0]
                i+=1

        templateName = formdata.pop('templateName')
        pp = pprint.PrettyPrinter(indent=4)
        # go thru configs
        for key, val in formdata.items():
            if key[0:7] == "package":
                # add new package
                if key[7] == "A":
                    # init new package
                    curpack = {}
                    curpack['type'] = "package"
                    curpack['matchvalue'] = val['Name']
                    curpack['config'] = []
                    curpack['change'] = {}
                    curpack['change']['add'] = []
                    curpack['change']['del'] = []

                    if val['Add']=="on":
                        metaconf['metaconf']['change']['add'].append(val['Name'])
                    for pkey in val.keys():
                        if pkey[0:6] == 'config':
                            if pkey[6] == "A":
                                mconfig = {}
                                config = mconfig
                                curconfig = val[pkey]
                                while True:
                                    if curconfig['Add']=='on':
                                        curpack['change']['add'].append(  \
                                            [curconfig['Name'], \
                                             curconfig['Type'], \
                                             curconfig['CreateType']])
                                    config['matchvalue']=curconfig['Name']
                                    config['matchtype']=curconfig['matchtype']
                                    config['matchcount']=curconfig['Count']
                                    config['type']='config'
                                    config['change']={}
                                    config['change']['add']=[]
                                    config['change']['del']=[]
                                    optsToAdd = [value for key, value in curconfig.items() if key.startswith('optA')]
                                    for opt in optsToAdd:
                                        config['change']['add'].append(\
                                                [opt['Name'], \
                                                 opt['Value']])
                                    optsToDel = [value for key, value in curconfig.items() if key.startswith('optD')]
                                    for opt in optsToDel:
                                        config['change']['del'].append(\
                                                opt['Name'])
                                    nextconfigs = [value for key, value in curconfig.items() if key.startswith('configA')]
                                    if nextconfigs:
                                        curconfig = nextconfigs[0]
                                        config['next'] = {}
                                        config = config['next']
                                    else:
                                        config['next'] = ''
                                        break
                                curpack['config'].append(mconfig)
                            if pkey[6] == "D":
                                curpack['change']['del'].append(  \
                                        [val[pkey]['Name'], \
                                         val[pkey]['Type'], \
                                         val[pkey]['DelType']])
                    metaconf['metaconf']['packages'].append(curpack)
                # delete package
                if key[7] == "D":
                    metaconf['metaconf']['change']['del'].append(val['Name'])
            else:
                print("ERROR: first level should be a package")
        pp.pprint(request.POST)
        pp.pprint(formdata)
        pp.pprint(metaconf)
        pp.pprint(templateName)
    return {}

@view_config(route_name='openwrt_action', renderer='templates/openwrt_add.jinja2', layout='base')
def openwrt_action(request):
    action = request.matchdict['action']
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()

    if action == 'delete':
        DBSession.delete(device)
        return HTTPFound(location=request.route_url('openwrt_list'))
    if action == 'getConfig':
        jobtask.get_config.delay(request.matchdict['uuid'])
        return HTTPFound(location=request.route_url('openwrt_list'))
    if action == 'saveConfToArchive':
        confToBeArchived = ConfigArchive(datetime.now(),device.configuration,device.uuid,id_generator())
        DBSession.add(confToBeArchived)
        return HTTPFound(location=request.route_url('confarchive'))

    return HTTPFound(location=request.route_url('openwrt_detail', uuid=request.matchdict['uuid']))

@jsonrpc_method(method='uuid_generate', endpoint='api')
def uuid_generate(request, unique_identifier):
    return {'uuid': generate_device_uuid(unique_identifier) }

@jsonrpc_method(method='get_node_status', endpoint='api')
def get_node_status(request, uuid):
    r = redis.StrictRedis(host=redishost, port=redisport, db=redisdb)
    resp = {}
    resp['status'] = r.hget(str(uuid), 'status').decode()
    resp['uuid']=uuid
    if resp['status'] == 'online':
        resp['interfaces'] = json.loads(r.hget(str(uuid), 'networkstatus').decode())
    return resp

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

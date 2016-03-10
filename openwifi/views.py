from pyramid.response import Response
from pyramid.view import view_config, forbidden_view_config
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
from wsgiproxy import Proxy

import json
from pyuci import Uci
import openwifi.jobserver.tasks as jobtask

from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.expression import func as sql_func

from .models import (
    AccessPoint,
    DBSession,
    OpenWrt,
    ConfigArchive,
    Templates,
    SshKey
    )

from .forms import (
        AccessPointAddForm,
        OpenWrtEditForm,
        LoginForm,
        SshKeyForm
        )

from .utils import generate_device_uuid

from pyramid.security import (
   Allow,
   Authenticated,
   remember,
   forget)

from pyramid_ldap3 import (
    get_ldap_connector,
    groupfinder)

@view_config(route_name='login',
             renderer='templates/login.jinja2',
	     layout='base')
@forbidden_view_config(renderer='templates/login.jinja2', layout='base')
def login(request):
    form = LoginForm(request.POST)
    save_url = request.route_url('login')

    if request.method == 'POST' and form.validate():
        login = form.login.data
        password = form.password.data
        print("login " + login + " password " + password); 
        connector = get_ldap_connector(request)
        data = connector.authenticate(login, password)
        if data is not None:
            print("data found!!")
            dn = data[0]
            headers = remember(request, dn)
            return HTTPFound(location=request.route_url('home'), headers=headers)
        else:
            print("wrong credentials")
            error = 'Invalid credentials'

    return {'save_url':save_url, 'form':form}

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return Response('Logged out', headers=headers)

@view_config(route_name='home', renderer='templates/home.jinja2', layout='base', permission='view')
def home(request):
    return {}

@view_config(route_name='confarchive', renderer='templates/archive_list.jinja2', layout='base', permission='view')
def confarchive(request):
    configs = DBSession.query(ConfigArchive)
    return {'idfield': 'id',
            'domain': 'confarchive',
            'items': configs,
            'table_fields': ['date', 'id', 'router_uuid', 'configuration'],
            'actions' : {'show config':'archive_edit_config',
                         'apply config':'archive_apply_config'}
            }

@view_config(route_name='archive_edit_config', renderer='templates/archive_edit_config.jinja2', layout='base', permission='view')
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

@view_config(route_name='archive_apply_config', renderer='templates/archive_apply_config.jinja2', layout='base', permission='view')
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
        name = str(device.name)
        while name in devices.keys():
            name += '_'
        devices[name] = str(device.uuid)
    return { 'devices' : devices,
             'checked' : [] }

openwrt_actions = ['delete', 'getConfig', 'saveConfToArchive'] 

@view_config(route_name='openwrt_list', renderer='templates/openwrt.jinja2', layout='base', permission='view')
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
            'table_fields': ['name', 'distribution', 'version', 'address', 'uuid','configuration', 'configured'],
            'actions' : openwrt_actions }

@view_config(route_name='openwrt_detail', renderer='templates/openwrt_detail.jinja2', layout='base', permission='view')
def openwrt_detail(request):
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()

    return {'device': device,
            'fields': ['name', 'distribution', 'version', 'address', 'uuid', 'login', 'password', 'templates'],
            'actions': openwrt_actions }

@view_config(route_name='openwrt_add', renderer='templates/openwrt_add.jinja2', layout='base', permission='view')
def openwrt_add(request):
    form = OpenWrtEditForm(request.POST)
    if request.method == 'POST' and form.validate():
        ap = OpenWrt(form.name.data, form.address.data, form.distribution.data, form.version.data, form.uuid.data, form.login.data, form.password.data, False)
        DBSession.add(ap)
        return HTTPFound(location=request.route_url('openwrt_list'))

    save_url = request.route_url('openwrt_add')
    return {'save_url':save_url, 'form':form}

@view_config(route_name='openwrt_edit_config', renderer='templates/openwrt_edit_config.jinja2', layout='base', permission='view')
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

def do_multi_openwrt_action(openwrts, action):
    for openwrt in openwrts:
        do_action_with_device(action, openwrt)

def do_action_with_device(action, device):
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

@view_config(route_name='openwrt_action', renderer='templates/openwrt_add.jinja2', layout='base', permission='view')
def openwrt_action(request):
    action = request.matchdict['action']
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()
    return do_action_with_device(action, device)

def generateMetaconfJson(POST):
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
        for key, val in POST.dict_of_lists().items():
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

                    try:
                        if val['Add']=="on":
                            metaconf['metaconf']['change']['add'].append(val['Name'])
                    except KeyError: #don't add if no key
                        pass
                    for pkey in val.keys():
                        if pkey[0:6] == 'config':
                            if pkey[6] == "A":
                                mconfig = {}
                                config = mconfig
                                curconfig = val[pkey]
                                while True:
                                    try:
                                        if curconfig['Add']=='on':
                                            curpack['change']['add'].append(  \
                                                [curconfig['Name'], \
                                                 curconfig['Type'], \
                                                 curconfig['CreateType']])
                                    except KeyError: # don't add if we have not received to add
                                        pass
                                    config['matchvalue']=curconfig['Name']
                                    config['matchtype']=curconfig['matchtype']
                                    config['ucitype']=curconfig['Type']
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
        pp.pprint(POST)
        pp.pprint(formdata)
        pp.pprint(metaconf)
        pp.pprint(templateName)
        metaconf_json = json.dumps(metaconf)
        return metaconf_json, templateName

@view_config(route_name='templates', renderer='templates/templates.jinja2', layout='base', permission='view')
def templates(request):
    templates = DBSession.query(Templates)
    openwrts = {}
    for template in templates:
        openwrts[template.id] = []
        for openwrt in template.openwrt:
            openwrts[template.id].append({ 'uuid' : openwrt.uuid, \
                                           'name' : openwrt.name})
    return {'items': templates,
            'openwrts' : openwrts,
            'table_fields': ['name', 'id', 'metaconf', 'openwrt'],
            'actions' : ['update']}

@view_config(route_name='templates_delete', renderer='templates/templates.jinja2', layout='base', permission='view')
def templates_delete(request):
    template = DBSession.query(Templates).get(request.matchdict['id'])
    if not template:
        return exc.HTTPNotFound()
    DBSession.delete(template)
    return HTTPFound(location=request.route_url('templates'))

@view_config(route_name='templates_edit', renderer='templates/templates_add.jinja2', layout='base', permission='view')
def templates_edit(request):
    template = DBSession.query(Templates).get(request.matchdict['id'])
    if not template:
        return exc.HTTPNotFound()
    if request.POST:
        metaconf_json, templateName = generateMetaconfJson(request.POST)
        template.metaconf = metaconf_json
        template.name = templateName
        return HTTPFound(location=request.route_url('templates'))
    return { 'metaconf' : template.metaconf,
             'templateName' : template.name}
    
@view_config(route_name='templates_add', renderer='templates/templates_add.jinja2', layout='base', permission='view')
def templates_add(request):
    if request.POST:
        metaconf_json, templateName = generateMetaconfJson(request.POST)
        newTemplate = Templates(templateName,metaconf_json,id_generator())
        DBSession.add(newTemplate)
        return HTTPFound(location=request.route_url('templates'))
    return {'metaconf' : '{}',
            'templateName':''}

@view_config(route_name='templates_assign', renderer='templates/archive_apply_config.jinja2', layout='base', permission='view')
def templates_assign(request):
    template = DBSession.query(Templates).get(request.matchdict['id'])
    if not template:
        return exc.HTTPNotFound()
    openwrt = DBSession.query(OpenWrt)
    devices = {}
    if request.POST:
        for ow in openwrt:
            try:
                ow.templates.remove(template)
            except ValueError: # if the template is not assoc - do nothing
                pass
        for name,value in request.POST.dict_of_lists().items():
            if name!='submitted':
                device = DBSession.query(OpenWrt).get(name)
                if  value: # if item is not the submit button and it's checkd
                    device.templates.append(template)
        return HTTPFound(location = request.route_url('templates'))
    for device in openwrt:
        name = str(device.name)
        while name in devices.keys():
            name += '_'
        devices[name] = str(device.uuid)
    checked = []
    for device in template.openwrt:
        checked.append(str(device.uuid))
    return { 'devices' : devices,
             'checked' : checked}

@view_config(route_name='templates_action', renderer='templates/templates.jinja2', layout='base', permission='view')
def templates_action(request):
    action = request.matchdict['action']
    template = DBSession.query(Templates).get(request.matchdict['id'])
    if not template:
        return exc.HTTPNotFound()

    if action == 'update':
        jobtask.update_template_config.delay(template.id)
        return HTTPFound(location=request.route_url('templates'))

    return exc.HTTPNotFound()



@view_config(route_name='sshkeys', renderer='templates/sshkeys.jinja2', layout='base', permission='view')
def sshkeys(request):
    sshkeys = DBSession.query(SshKey)
    openwrts = {}
    for sshkey in sshkeys:
        openwrts[sshkey.id] = []
        for openwrt in sshkey.openwrt:
            openwrts[sshkey.id].append({ 'uuid' : openwrt.uuid, \
                                           'name' : openwrt.name})
    return { 'items' : sshkeys,
	     'openwrts' : openwrts,
             'table_fields' : ['id', 'key', 'comment', 'openwrt' ,'actions'],
             'actions' : ['delete']}

@view_config(route_name='sshkeys_add', renderer='templates/sshkeys_add.jinja2', layout='base', permission='view')
def sshkeys_add(request):
    form = SshKeyForm(request.POST)
    if request.method == 'POST' and form.validate():
        query = DBSession.query(sql_func.max(SshKey.id)) 
        try: 
            max = int(query[0][0])
        except:
            max = 0
        sshkey = SshKey(form.key.data, form.comment.data, max+1)
        DBSession.add(sshkey)
        return HTTPFound(location=request.route_url('sshkeys'))
    save_url = request.route_url('sshkeys_add')
    return {'save_url':save_url, 'form':form}


@view_config(route_name='sshkeys_assign', renderer='templates/archive_apply_config.jinja2', layout='base', permission='view')
def sshkeys_assign(request):
    sshkey = DBSession.query(SshKey).get(request.matchdict['id'])
    if not sshkey:
        return exc.HTTPNotFound()
    openwrt = DBSession.query(OpenWrt)
    devices = {}
    if request.POST:
        devices_to_be_updated = []
        for ow in openwrt:
            try:
                ow.ssh_keys.remove(sshkey)
                devices_to_be_updated.append(ow.uuid)
            except ValueError: # if the template is not assoc - do nothing
                pass
        for name,value in request.POST.dict_of_lists().items():
            if name!='submitted':
                device = DBSession.query(OpenWrt).get(name)
                if  value: # if item is not the submit button and it's checkd
                    device.ssh_keys.append(sshkey)
                    devices_to_be_updated.append(device.uuid)
        transaction.commit()
        for update_device in set(devices_to_be_updated):
            jobtask.update_openwrt_sshkeys.delay(update_device)
        return HTTPFound(location = request.route_url('sshkeys'))
    for device in openwrt:
        name = str(device.name)
        while name in devices.keys():
            name += '_'
        devices[name] = str(device.uuid)
    checked = []
    for device in sshkey.openwrt:
        checked.append(str(device.uuid))
    return { 'devices' : devices,
             'checked' : checked}

@view_config(route_name='sshkeys_action', renderer='templates/sshkeys.jinja2', layout='base', permission='view')
def sshkeys_action(request):
    action = request.matchdict['action']
    id = request.matchdict['id']
    sshkey = DBSession.query(SshKey).get(id)
    if not sshkey:
        return exc.HTTPNotFound()
    if action == 'delete':
        DBSession.delete(sshkey)
        return HTTPFound(location=request.route_url('sshkeys'))
    return { 'keys' : sshkeys }

@view_config(route_name='luci', renderer='templates/luci.jinja2', layout='base', permission='view')
def luci2(request):
    print(request)
    uuid=request.matchdict['uuid']
    return {"uuid":uuid}

@view_config(route_name='ubus',renderer="json", permission='view')
def ubus(request):
    command = request.matchdict['command']
    print(command)
    if len(command)>0:
        command = command[0]
    else:
    	command=False
    uuid = request.matchdict['uuid']
    #print(request)
    #print(request.environ)
    proxy = Proxy()
    address=DBSession.query(OpenWrt).get(uuid).address
    #address='192.168.50.124'
    #request.environ["PATH_INFO"]="ubus/"+request.environ["PATH_INFO"].split('/')[-1]
    #request.environ["SERVER_NAME"]='192.168.50.116'
    #request.environ["SERVER_PORT"]=80
    request.server_port=80
    request.server_name=address
    request.host_name=address
    if command:
	    request.upath_info='/ubus/'+request.upath_info.split('/')[-1]
    else:
	    request.upath_info='/ubus'
    #print(request.url)
    #print(request.application_url)
    #print(request.path)
    #print(request.upath_info)
    #print(request.environ)
    res=request.get_response(proxy)
    #print(res.app_iter)
    #print(res)
    #print(str(res))
    return json.loads(res.app_iter[0].decode('utf8'))

@jsonrpc_method(endpoint='api')
def hello(request):
    """ this call is used for discovery to ensure """
    return "openwifi"

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

@jsonrpc_method(method='device_register', endpoint='api')
def device_register(request, uuid, name, address, distribution, version, proto, login, password):
    device = DBSession.query(OpenWrt).get(uuid)
    # if uuid exists, update information
    if device:
    # otherwise add new device
        device.name = name
        device.address = address
        device.distribution = distribution
        device.version = version
        device.proto = proto
        device.login = login
        device.password = password
    else:
        ap = OpenWrt(name, address, distribution, version, uuid, login, password, False)
        DBSession.add(ap)
    DBSession.flush()

@jsonrpc_method(method='device_check_registered', endpoint='api')
def device_check_registered(request, uuid, name):
    """
    check if a device is already present in database. This call is used by a device to check if it must register again.
    """
    device = DBSession.query(OpenWrt).get(uuid)
    if device:
        return True
    else:
        return False

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

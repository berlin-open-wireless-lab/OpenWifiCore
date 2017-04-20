from pyramid.response import Response
from pyramid.view import view_config, forbidden_view_config
from pyramid.httpexceptions import HTTPFound
from pyramid_rpc.jsonrpc import jsonrpc_method
from pyramid import httpexceptions as exc
import transaction
from datetime import datetime
import pprint
from openwifi.jobserver_config import redishost, redisport, redisdb
import redis
from wsgiproxy import Proxy

import shutil
import os

import json
from pyuci import Uci
import openwifi.jobserver.tasks as jobtask
from openwifi.utils import id_generator

from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.expression import func as sql_func

from .models import (
    AccessPoint,
    DBSession,
    OpenWrt,
    ConfigArchive,
    Templates,
    SshKey,
    OpenWifiSettings
    )

from .utils import generate_device_uuid

from pyramid.security import (
   Allow,
   Authenticated,
   remember,
   forget)

@jsonrpc_method(endpoint='api')
def hello(request):
    """ this call is used for discovery to ensure """
    return "openwifi"

@jsonrpc_method(method='uuid_generate', endpoint='api')
def uuid_generate(request, unique_identifier):
    return {'uuid': generate_device_uuid(unique_identifier) }

@jsonrpc_method(method='get_default_image_url', endpoint='api')
def get_default_image_url(request, uuid):
    baseImageUrl = DBSession.query(OpenWifiSettings).get('baseImageUrl')
    baseImageChecksumUrl = DBSession.query(OpenWifiSettings).get('baseImageChecksumUrl')
    if baseImageUrl and baseImageChecksumUrl:
        return {'default_image' : baseImageUrl.value, 
                'default_checksum' : baseImageChecksumUrl.value}
    else:
        return False

@jsonrpc_method(method='get_node_status', endpoint='api')
def get_node_status(request, uuid):
    r = redis.StrictRedis(host=redishost, port=redisport, db=redisdb)
    resp = {}
    status = r.hget(str(uuid), 'status')
    if status: 
        resp['status'] = status.decode()
    else:
        resp['status'] = 'no status information available'
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

    for devRegFunc in request.registry.settings['OpenWifi.onDeviceRegister']:
        devRegFunc(uuid)

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

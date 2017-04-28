import json
from .utils import generate_device_uuid_str, id_generator

from .models import (
    DBSession,
    OpenWrt
    )

from openwifi.jobserver.tasks import exec_on_device

from cornice import Service
from cornice.resource import resource

@resource(collection_path='/nodes', path='/nodes/{UUID}')
class Nodes(object):

    def __init__(self, request):
        self.request = request

    def collection_get(self):
        uuids = []
        for openwrt in DBSession.query(OpenWrt):
            uuids.append(str(openwrt.uuid))
        return uuids

    # add new openwifi node
    def collection_post(self):
        newNodeData = json.loads(self.request.body.decode())
        if 'uuid' in newNodeData.keys() and newNodeData['uuid']:
            uuid = newNodeData['uuid']
        else:
            uuid = generate_device_uuid_str(id_generator())
        ap = OpenWrt(newNodeData['name'], newNodeData['address'], newNodeData['distribution'], newNodeData['version'], uuid, newNodeData['login'], newNodeData['password'], False)
        DBSession.add(ap)
        return str(ap.uuid)

    def get(self):
        uuid = self.request.matchdict['UUID']
        openwrt = DBSession.query(OpenWrt).get(uuid)

        return openwrt.jsonParsable()

    # modify node TODO: add validator
    def post(self):
        uuid = self.request.matchdict['UUID']
        openwrt = DBSession.query(OpenWrt).get(uuid)

        if not openwrt:
            return False

        modData = json.loads(self.request.body.decode())

        for key, value in modData.items():
            openwrt.setData(key, value)

        return True

    def delete(self):
        uuid = self.request.matchdict['UUID']
        openwrt = DBSession.query(OpenWrt).get(uuid)
        if openwrt:
            DBSession.delete(openwrt)
            return True
        else:
            return False


execService = Service(name='execOnNode',
                      path='/nodes/{UUID}/exec',
                      description='execute command on node')

@execService.get()
def get_execService(request):
    usage = {'command' : 'command do execute',
             'params' : ['list','of','params']}

    return usage

@execService.post()
def post_execService(request):
    query = json.loads(request.body.decode())
    uuid = request.matchdict['UUID']

    r = exec_on_device.delay(uuid, query['command'], query['params'])
    return request.route_url('execStatus', UUID=r.id)

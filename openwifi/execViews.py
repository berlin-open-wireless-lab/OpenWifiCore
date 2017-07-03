from pyramid.view import view_config
from openwifi.jobserver.tasks import exec_on_device

@view_config(route_name='execStatus', renderer='json', permission='node_access')
def execStatus(request):
    id = request.matchdict['UUID']
    r = exec_on_device.AsyncResult(id)
    ret = {}
    ret['status'] = r.status
    
    if r.status == "SUCCESS":
        ret['result'] = r.result

    return ret

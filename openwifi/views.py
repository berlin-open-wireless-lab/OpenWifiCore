from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid_rpc.jsonrpc import jsonrpc_method
from pyramid import httpexceptions as exc

from sqlalchemy.exc import DBAPIError

from .models import (
    AccessPoint,
    DBSession,
    OpenWrt,
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
    return {'idfield': 'uuid',
            'domain': 'openwrt',
            'items': openwrt,
            'table_fields': ['name', 'distribution', 'version', 'address', 'uuid']}

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
            'actions': ['delete']}

@view_config(route_name='openwrt_add', renderer='templates/openwrt_add.jinja2', layout='base')
def openwrt_add(request):
    form = OpenWrtEditForm(request.POST)
    if request.method == 'POST' and form.validate():
        ap = OpenWrt(form.name.data, form.address.data, form.distribution.data, form.version.data, form.uuid.data, False)
        DBSession.add(ap)
        return HTTPFound(location=request.route_url('openwrt_list'))

    save_url = request.route_url('openwrt_add')
    return {'save_url':save_url, 'form':form}

@view_config(route_name='openwrt_action', renderer='templates/openwrt_add.jinja2', layout='base')
def openwrt_action(request):
    action = request.matchdict['action']
    device = DBSession.query(OpenWrt).get(request.matchdict['uuid'])
    if not device:
        return exc.HTTPNotFound()

    if action == 'delete':
        DBSession.delete(device)
        return HTTPFound(location=request.route_url('openwrt_list'))

    return HTTPFound(location=request.route_url('openwrt_detail', uuid=request.matchdict['uuid']))

@jsonrpc_method(method='uuid_generate', endpoint='api')
def uuid_generate(request, unique_identifier):
    return {'uuid': generate_device_uuid(unique_identifier) }

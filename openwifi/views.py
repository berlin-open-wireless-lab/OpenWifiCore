from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    AccessPoint,
    )

from .forms import (
        AccessPointAddForm,
        )

@view_config(route_name='home', renderer='templates/home.jinja2', layout='base')
def home(request):
    return {}

@view_config(route_name='accesspoint_list', renderer='templates/accesspoints.jinja2', layout='base')
def accesspoints_list(request):
    accesspoints = DBSession.query(AccessPoint)
    return { 'items': accesspoints, 'table_fields': ['id', 'name', 'hardware', 'radio', 'address'] }

@view_config(route_name='accesspoint_add', renderer='templates/accesspoints_add.jinja2', layout='base')
def accesspoints_add(request):
    form = AccessPointAddForm(request.POST)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        hardware = form.hardware.data
        radio_amount_2g = form.radios_2g.data
        radio_amount_5g = form.radios_5g.data
        address = form.address.data

        ap = AccessPoint(name, address, hardware, radio_amount_2g, radio_amount_5g)
        DBSession.add(ap)
        return HTTPFound(location = request.route_url('accesspoint_list'))

    save_url = request.route_url('accesspoint_add')
    return { 'save_url':save_url, 'form':form }

@view_config(route_name='accesspoint_edit', renderer='templates/accesspoints_edit.jinja2', layout='base')
def accesspoints_edit(request):
    form = AccessPointEditForm(request.POST)
    ap = DBSession.query(AccessPoint).filter_by(id=ap_id).one()
    if request.method == 'POST' and form.validate():
        ap.hardware = 'changed hardware'
        return HTTPFound(locaton = request.route_url('accesspoint_list'))
    
    return { 'form': form }

@view_config(route_name='station_list', renderer='templates/simple_list.jinja2', layout='base')
def station_list(request):
    stations = []
    return { 'items': stations, 'table_fields': ['id', 'name', 'hardware', 'band', 'address'] }


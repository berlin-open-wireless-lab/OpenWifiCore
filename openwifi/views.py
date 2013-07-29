from pyramid.response import Response
from pyramid.view import view_config

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
    return { 'items': accesspoints, 'table_fields': ['id', 'name', 'host'] }

@view_config(route_name='accesspoint_item', renderer='templates/accesspoints_item.jinja2', layout='base')
def accesspoints_item(request):
    return {}

@view_config(route_name='accesspoint_add', renderer='templates/accesspoints_add.jinja2', layout='base')
def accesspoints_add(request):
    form = AccessPointAddForm(request.POST)
    if request.method == 'POST' and form.validate():
        name = request.params['name']
        hardware = request.params['hardware']
        radio_amount_2ghz = request.params['2ghz']
        radio_amount_5ghz = request.params['5ghz']
        #page = Page(pagename, body)
        ap = AccessPoint(name, hardware, radio_amount_2ghz, radio_amount_5ghz)
        #DBSession.add(page)
        return HTTPFound(location = request.route_url('view_page',
                name=name))

    save_url = request.route_url()
    return {}

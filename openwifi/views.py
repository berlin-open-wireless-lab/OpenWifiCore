from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    )

@view_config(route_name='home', renderer='templates/home.jinja2', layout='base')
def home(request):
    return {}

@view_config(route_name='accesspoint_list', renderer='templates/accesspoints.jinja2', layout='base')
def accesspoints_list(request):
    return {}

@view_config(route_name='accesspoint_item', renderer='templates/accesspoints_item.jinja2', layout='base')
def accesspoints_item(request):
    return {}

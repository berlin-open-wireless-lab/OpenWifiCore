from pyramid.view import view_config, forbidden_view_config
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.security import remember, forget
from pyramid.request import Response

def auth_ldap(request, login, password):
    from pyramid_ldap3 import (
        get_ldap_connector,
        groupfinder)

    connector = get_ldap_connector(request)
    data = connector.authenticate(login, password)
    if data is not None:
        dn = data[0]
        headers = remember(request, dn)
        return HTTPFound(location=request.route_url('home'), headers=headers)
    else:
        return HTTPForbidden()

def auth_openwifi(request, login, password):
    from openwifi.authentication import check_password

    if check_password(login, password):
        headers = remember(request, login)
        return HTTPFound(location=request.route_url('home'), headers=headers)
    else:
        return HTTPForbidden()

def auth(request, login, password):
    from pyramid.settings import asbool
    settings = request.registry.settings

    if asbool(settings.get('openwifi.useLDAP')):
        return auth_ldap(request, login, password)

    if asbool(settings.get('openwifi.useAuth')):
        return auth_openwifi(request, login, password)


@view_config(route_name='login', renderer='json', request_method='POST')
def login_post(request):
    data = request.json_body
    login = data['login']
    password = data['password']

    return auth(request, login, password)

@view_config(route_name='login', renderer='json', request_method='GET', effective_principals='group:users')
def login_logged_in(request):
    return True

@view_config(route_name='login', renderer='json', request_method='GET')
def login_not_logged_in(request):
    from openwifi.authentication import auth_used
    if auth_used(request):
        return False
    else:
        return True

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)
